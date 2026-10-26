"""Authentication controls: password hashing, enumeration resistance, sessions and MFA."""

import time

from app.core import security
from app.core.security import get_password_hash, legacy_pwd_context, verify_password
from app.documents import User


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
