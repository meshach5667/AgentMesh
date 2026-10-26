"""Authentication controls: password hashing, enumeration resistance, sessions and MFA."""

import asyncio
import time
import uuid
from datetime import timedelta

import jwt

from app.core import security
from app.core.config import settings
from app.core.keys import derive_key
from app.core.security import (
    ALGORITHM,
    TOKEN_AUDIENCE,
    create_access_token,
    get_password_hash,
    legacy_pwd_context,
    verify_password,
)
from app.documents import AuditLog, AuthSession, User


async def test_passwords_are_hashed_with_argon2id(client, db):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "new@example.com", "password": "a-long-password", "role": "customer"}
    )
    assert resp.status_code == 200, resp.text
    user = await db.find_one(User, {"email": "new@example.com"})
    assert user.hashed_password.startswith("$argon2id$")
    assert "a-long-password" not in user.hashed_password
    assert verify_password("a-long-password", user.hashed_password)
    assert not verify_password("wrong", user.hashed_password)
    assert not verify_password("a-long-password", None) and not verify_password("x", "garbage")


async def test_legacy_pbkdf2_hash_still_works_and_is_upgraded_at_login(client, db):
    legacy = legacy_pwd_context.hash("old-password-1", scheme="pbkdf2_sha256")
    db.add(User(email="old@example.com", hashed_password=legacy, role="customer"))
    await db.commit()
    resp = await client.post("/api/v1/auth/login", json={"email": "old@example.com", "password": "old-password-1"})
    assert resp.status_code == 200, resp.text
    db.expire_all()
    user = await db.find_one(User, {"email": "old@example.com"})
    assert user.hashed_password.startswith("$argon2id$")
    assert (
        await client.post("/api/v1/auth/login", json={"email": "old@example.com", "password": "old-password-1"})
    ).status_code == 200


async def test_unknown_email_costs_a_password_check_and_gets_the_same_answer(client, db, monkeypatch):
    db.add(User(email="real@example.com", hashed_password=get_password_hash("right-password"), role="customer"))
    await db.commit()
    calls = []
    real = security.burn_password_check
    monkeypatch.setattr("app.services.auth_service.burn_password_check", lambda p: calls.append(p) or real(p))

    async def attempt(email):
        start = time.perf_counter()
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
        return resp, time.perf_counter() - start

    known, t_known = await attempt("real@example.com")
    unknown, t_unknown = await attempt("ghost@example.com")
    assert known.status_code == unknown.status_code == 401
    assert known.json() == unknown.json()
    assert calls == ["wrong-password"]  # the unknown email still paid for an Argon2 verification
    assert t_unknown > 0.5 * t_known  # same order of cost (an unhashed path would be ~100x faster)


async def test_legacy_node_registration_keys_use_a_fast_secret_hash(client, db, make_user):
    from app.documents import Node

    _, provider = await make_user("provider")
    body = {"name": "legacy", "public_key": "pem", "region": "eu-west"}
    resp = await client.post("/api/v1/nodes/register", json=body, headers=provider)
    assert resp.status_code in (200, 201), resp.text
    node = await db.get(Node, __import__("uuid").UUID(resp.json()["id"]))
    assert node.api_key_hash.startswith("sha256$")
    beat = await client.post(
        f"/api/v1/nodes/{node.id}/heartbeat", headers={"Authorization": f"Bearer {resp.json()['api_key']}"}
    )
    assert beat.status_code == 200, beat.text


# --- sessions and refresh tokens (G-04) ---------------------------------------------------------------------


async def _refresh(client, token):
    return await client.post("/api/v1/auth/refresh", json={"refresh_token": token})


async def _login(client, db, email="sess@example.com", password="session-password"):
    if not await db.find_one(User, {"email": email}):
        db.add(User(email=email, hashed_password=get_password_hash(password), role="customer"))
        await db.commit()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_access_tokens_are_short_lived_and_bound_to_a_session(client, db):
    tokens = await _login(client, db)
    claims = jwt.decode(tokens["access_token"], options={"verify_signature": False})
    assert (
        claims["exp"] - claims["iat"] <= 15 * 60 and tokens["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    assert claims["typ"] == "access" and claims["aud"] == TOKEN_AUDIENCE
    session = await db.get(AuthSession, uuid.UUID(claims["sid"]))
    assert session is not None and session.revoked_at is None
    assert tokens["refresh_token"].startswith("am_rt_") and tokens["refresh_token"] not in str(session.model_dump())


async def test_refresh_rotates_and_reuse_revokes_the_whole_session(client, db):
    first = await _login(client, db)
    second = (await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})).json()
    assert second["refresh_token"] != first["refresh_token"]
    assert (await client.get("/api/v1/auth/me", headers=_bearer(second))).status_code == 200

    # The first refresh token was copied by an attacker and is presented again: everything in the session dies.
    stolen = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert stolen.status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=_bearer(second))).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]})
    ).status_code == 401
    db.expire_all()
    revoked = await db.find_one(AuditLog, {"action": "auth.session_revoked"})
    assert revoked.details["reason"] == "refresh_token_reuse"


async def test_concurrent_use_of_one_refresh_token_yields_at_most_one_new_token(client, db):
    tokens = await _login(client, db)
    results = await asyncio.gather(
        *[client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}) for _ in range(4)]
    )
    assert sum(r.status_code == 200 for r in results) <= 1
    assert all(r.status_code in (200, 401, 409) for r in results)


async def test_logout_and_logout_all_take_effect_immediately(client, db):
    a = await _login(client, db)
    b = await _login(client, db)
    assert (await client.post("/api/v1/auth/logout", headers=_bearer(a))).status_code == 204
    assert (await client.get("/api/v1/auth/me", headers=_bearer(a))).status_code == 401
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": a["refresh_token"]})).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=_bearer(b))).status_code == 200  # other device unaffected
    c = await _login(client, db)
    ended = (await client.post("/api/v1/auth/logout-all", headers=_bearer(c))).json()["sessions_ended"]
    assert ended == 2
    for t in (b, c):
        assert (await client.get("/api/v1/auth/me", headers=_bearer(t))).status_code == 401


async def test_disabled_account_loses_access_and_refresh(client, db):
    tokens = await _login(client, db)
    user = await db.find_one(User, {"email": "sess@example.com"})
    user.is_active = False
    await db.commit()
    assert (await client.get("/api/v1/auth/me", headers=_bearer(tokens))).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 401


async def test_malformed_expired_and_foreign_tokens_are_rejected(client, db):
    tokens = await _login(client, db)
    claims = jwt.decode(tokens["access_token"], options={"verify_signature": False})
    key = derive_key("access-token")
    good = {k: claims[k] for k in ("sub", "sid", "typ", "aud", "iat", "exp")}
    bad_tokens = {
        "expired": create_access_token(claims["sub"], claims["sid"], expires_delta=timedelta(minutes=-5)),
        "tampered": tokens["access_token"][:-4] + ("AAAA" if not tokens["access_token"].endswith("AAAA") else "BBBB"),
        "old_format_raw_secret": jwt.encode(
            {"sub": claims["sub"], "exp": claims["exp"]}, settings.SECRET_KEY, ALGORITHM
        ),
        "wrong_type": jwt.encode(good | {"typ": "mfa"}, key, ALGORITHM),
        "wrong_audience": jwt.encode(good | {"aud": "elsewhere"}, key, ALGORITHM),
        "missing_session": jwt.encode({k: v for k, v in good.items() if k != "sid"}, key, ALGORITHM),
        "unknown_session": jwt.encode(good | {"sid": str(uuid.uuid4())}, key, ALGORITHM),
        "other_users_session": jwt.encode(good | {"sub": str(uuid.uuid4())}, key, ALGORITHM),
        "alg_none": jwt.encode(good, None, algorithm="none"),
        "garbage": "not.a.token",
    }
    for name, token in bad_tokens.items():
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401, name
    for bad in ("am_rt_unknown-token-value", "not-a-refresh-token", "am_rt_" + "x" * 150):
        assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": bad})).status_code == 401


# --- second factor for staff (G-05) ---------------------------------------------------------------------------


async def _staff(client, db, role, email, password):
    if not await db.find_one(User, {"email": email}):
        db.add(User(email=email, hashed_password=get_password_hash(password), role=role))
        await db.commit()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_staff_without_a_second_factor_reach_nothing_but_mfa_setup(client, db, make_user, approved_model):
    from tests.test_authorization import _deployment_for

    customer, _ = await make_user("customer")
    dep = await _deployment_for(db, customer, approved_model)
    tokens = await _staff(client, db, "admin", "admin@example.com", "admin-password-1")
    h = _bearer(tokens)
    me = (await client.get("/api/v1/auth/me", headers=h)).json()
    assert me["mfa_required"] is True and me["mfa_verified"] is False and me["mfa_enabled"] is False
    for path in ("/api/v1/admin/overview", f"/api/v1/deployments/{dep.id}", "/api/v1/admin/audit-logs"):
        resp = await client.get(path, headers=h)
        assert resp.status_code == 403 and resp.json()["detail"]["code"] == "mfa_required", path


async def test_enrolment_stores_an_encrypted_seed_and_unlocks_the_session(client, db):
    from tests.mfa_support import totp_code

    h = _bearer(await _staff(client, db, "operator", "op@example.com", "op-password-1"))
    secret = (await client.post("/api/v1/auth/mfa/setup", headers=h)).json()["secret"]
    assert (await client.post("/api/v1/auth/mfa/enable", json={"code": "000000"}, headers=h)).status_code == 401
    assert (
        await client.post("/api/v1/auth/mfa/enable", json={"code": totp_code(secret)}, headers=h)
    ).status_code == 204
    assert (await client.get("/api/v1/admin/overview", headers=h)).status_code == 200
    db.expire_all()
    user = await db.find_one(User, {"email": "op@example.com"})
    assert (
        user.mfa_secret.startswith("aesgcm:v1:") and secret not in user.mfa_secret and user.mfa_pending_secret is None
    )
    assert (await client.post("/api/v1/auth/mfa/setup", headers=h)).status_code == 409
    # Staff cannot switch it off again.
    code = totp_code(secret, time.time() + 30)
    assert (await client.post("/api/v1/auth/mfa/disable", json={"code": code}, headers=h)).status_code == 403
    actions = {a.action for a in await db.find(AuditLog, {"user_id": user.id})}
    assert "auth.mfa_enabled" in actions


async def test_login_with_a_second_factor(client, db):
    from tests.mfa_support import enroll_mfa, totp_code

    h = _bearer(await _staff(client, db, "operator", "op2@example.com", "op-password-2"))
    secret = await enroll_mfa(client, h)
    first = await client.post("/api/v1/auth/login", json={"email": "op2@example.com", "password": "op-password-2"})
    challenge = first.json()
    assert challenge["mfa_required"] is True and "access_token" not in challenge and "refresh_token" not in challenge
    # The challenge token is not an access token.
    assert (
        await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {challenge['mfa_token']}"})
    ).status_code == 401

    bad = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": challenge["mfa_token"], "code": "123456"})
    assert bad.status_code == 401
    code = totp_code(secret, time.time() + 30)  # next step: the enrolment code's step is already used
    ok = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": challenge["mfa_token"], "code": code})
    assert ok.status_code == 200, ok.text
    assert (await client.get("/api/v1/admin/overview", headers=_bearer(ok.json()))).status_code == 200
    # The same code cannot complete a second sign-in.
    again = await client.post("/api/v1/auth/login", json={"email": "op2@example.com", "password": "op-password-2"})
    replay = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": again.json()["mfa_token"], "code": code})
    assert replay.status_code == 401
    failed = await db.find(AuditLog, {"action": "auth.mfa_failed"})
    assert len(failed) == 2


async def test_expired_or_forged_challenge_tokens_are_refused(client, db):
    from app.services import mfa_service

    user = User(email="c3@example.com", hashed_password="x", role="operator", mfa_secret="aesgcm:v1:derived:AAAA")
    db.add(user)
    await db.commit()
    expired = jwt.encode(
        {"sub": str(user.id), "typ": "mfa", "aud": TOKEN_AUDIENCE, "iat": 1, "exp": 2},
        derive_key("mfa-challenge"),
        ALGORITHM,
    )
    access_key_token = jwt.encode(
        jwt.decode(mfa_service.challenge_token(user), options={"verify_signature": False}),
        derive_key("access-token"),
        ALGORITHM,
    )
    for token in (expired, access_key_token, "x" * 40):
        resp = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": token, "code": "123456"})
        assert resp.status_code == 401


async def test_customers_may_turn_a_second_factor_on_and_off(client, db):
    from tests.mfa_support import enroll_mfa, totp_code

    h = _bearer(await _login(client, db, email="cust-mfa@example.com", password="cust-password-1"))
    me = (await client.get("/api/v1/auth/me", headers=h)).json()
    assert me["mfa_required"] is False
    secret = await enroll_mfa(client, h)
    code = totp_code(secret, time.time() + 30)
    assert (await client.post("/api/v1/auth/mfa/disable", json={"code": code}, headers=h)).status_code == 204
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "cust-mfa@example.com", "password": "cust-password-1"}
    )
    assert "access_token" in resp.json()


def test_encrypted_values_are_bound_to_their_context_and_key(monkeypatch):
    import base64

    import pytest

    from app.core import crypto

    sealed = crypto.encrypt(b"seed-bytes", "user:a:totp")
    assert crypto.decrypt(sealed, "user:a:totp") == b"seed-bytes"
    for bad in (
        lambda: crypto.decrypt(sealed, "user:b:totp"),  # moved to another user's record
        lambda: crypto.decrypt(sealed[:-6] + "AAAAAA", "user:a:totp"),  # tampered
        lambda: crypto.decrypt("aesgcm:v1:unknown:AAAA", "user:a:totp"),
        lambda: crypto.decrypt("plaintext", "user:a:totp"),
    ):
        with pytest.raises(ValueError):
            bad()
    # A dedicated key takes over for new values; old ones stay readable.
    monkeypatch.setattr(settings, "DATA_ENCRYPTION_KEY", base64.b64encode(b"k" * 32).decode())
    new = crypto.encrypt(b"x", "c")
    assert (
        ":dek1:" in new and crypto.decrypt(new, "c") == b"x" and crypto.decrypt(sealed, "user:a:totp") == b"seed-bytes"
    )


def test_data_encryption_key_must_be_32_bytes():
    import base64

    import pytest
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError, match="DATA_ENCRYPTION_KEY"):
        Settings(DATA_ENCRYPTION_KEY=base64.b64encode(b"short").decode(), ENVIRONMENT="test", _env_file=None)
