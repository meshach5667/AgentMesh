"""Hostile input at the trust boundaries (security tests 14, 16, 17, 18): oversized, malformed and malicious bodies
are refused without leaking internals; mass assignment cannot set roles, owners, prices or usage; outbound fetches
cannot be pointed at internal addresses; production configuration disables debug features."""

import uuid

import httpx
import pytest
from fastapi import HTTPException

from app.core.config import Settings, settings
from app.documents import Deployment, Node, User
from app.services import huggingface

LEAK_MARKERS = ("Traceback", 'File "', "pymongo", "/home/", "site-packages", "mongodb://", "SECRET")


def _no_leak(resp: httpx.Response) -> None:
    for marker in LEAK_MARKERS:
        assert marker not in resp.text, f"{marker!r} leaked in a {resp.status_code} response"


# --- 14: oversized, malformed, malicious input ----------------------------------------------------------------


async def test_oversized_bodies_are_refused_before_parsing(client, make_user):
    _, customer = await make_user("customer")
    huge = "x" * (settings.GATEWAY_MAX_BODY_BYTES + 128 * 1024)
    resp = await client.post(
        "/api/v1/deployments", content=huge, headers=customer | {"Content-Type": "application/json"}
    )
    assert resp.status_code == 413
    _no_leak(resp)
    worker = await client.post("/api/v1/worker/heartbeat", content="y" * (settings.WORKER_MAX_BODY_BYTES + 1))
    assert worker.status_code == 413


@pytest.mark.parametrize(
    "body",
    ids=["broken", "deeply-nested", "control-bytes", "operator-injection", "long-string"],
    argvalues=[
        b"{not json",
        b'{"model_id": ' + b"[" * 5000 + b"]" * 5000 + b"}",  # deeply nested
        b'{"model_id": "\x00\xff"}',
        b'{"model_id": {"$ne": null}}',  # NoSQL operator injection
        b'{"model_id": "' + b"a" * 100_000 + b'"}',
    ],
)
async def test_malformed_and_injection_bodies_get_a_clean_4xx(client, make_user, body):
    _, customer = await make_user("customer")
    resp = await client.post(
        "/api/v1/deployments", content=body, headers=customer | {"Content-Type": "application/json"}
    )
    assert 400 <= resp.status_code < 500
    _no_leak(resp)


async def test_operator_injection_in_login_and_queries_is_inert(client, db, make_user):
    db.add(User(email="victim@example.com", hashed_password="x", role="customer"))
    await db.commit()
    for body in ({"email": {"$ne": None}, "password": "x"}, {"email": "victim@example.com", "password": {"$gt": ""}}):
        resp = await client.post("/api/v1/auth/login", json=body)
        assert resp.status_code == 422
    _, operator = await make_user("operator")
    resp = await client.get("/api/v1/admin/audit-logs?action[$ne]=x", headers=operator)
    assert resp.status_code in (200, 422)
    _no_leak(resp)


async def test_unhandled_errors_return_a_generic_500(client, make_user, monkeypatch):
    from app.services import reporting_service

    async def boom(*args, **kwargs):
        raise RuntimeError("mongodb://admin:SECRET@internal-db:27017 exploded")

    monkeypatch.setattr(reporting_service, "usage_summary", boom)
    _, customer = await make_user("customer")
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t") as c:
        resp = await c.get("/api/v1/usage/summary", headers=customer)
    assert resp.status_code == 500 and resp.text == "Internal Server Error"
    _no_leak(resp)


# --- 16: mass assignment and privilege escalation -------------------------------------------------------------


async def test_deployment_fields_set_by_the_server_cannot_be_supplied(client, db, make_user, ollama_model, enroll_node):
    node = await enroll_node()
    _, customer = await make_user("customer")
    other = uuid.uuid4()
    resp = await client.post(
        "/api/v1/deployments",
        json={
            "model_id": str(ollama_model.id),
            "customer_id": str(other),
            "node_id": node["node_id"],
            "status": "READY",
            "price": "0",
            "endpoint": "https://evil.example",
        },
        headers=customer,
    )
    assert resp.status_code in (200, 201), resp.text
    dep = await db.get(Deployment, uuid.UUID(resp.json()["id"]))
    assert dep.customer_id != other and dep.status != "READY" and dep.endpoint != "https://evil.example"
    bad = await client.post(
        "/api/v1/deployments",
        json={"model_id": str(ollama_model.id), "config": {"num_ctx": 2048, "node_id": node["node_id"]}},
        headers=customer,
    )
    assert bad.status_code == 422  # unknown deployment options are refused, not passed through


async def test_roles_owners_and_capacity_cannot_be_self_assigned(client, db, make_user, enroll_node):
    for role in ("admin", "operator"):
        resp = await client.post(
            "/api/v1/auth/register", json={"email": f"{role}@example.com", "password": "long-password", "role": role}
        )
        assert resp.status_code == 422
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "sneaky@example.com",
            "password": "long-password",
            "role": "customer",
            "is_active": True,
            "mfa_secret": "x",
        },
    )
    user = await db.find_one(User, {"email": "sneaky@example.com"})
    assert user.role == "customer" and user.mfa_secret is None

    node = await enroll_node()
    stranger = uuid.uuid4()
    for body in ({"owner_id": str(stranger)}, {"status": "ONLINE"}, {"reserved_ram_mb": 0}, {"quarantined_at": None}):
        resp = await client.patch(f"/api/v1/nodes/{node['node_id']}", json=body, headers=node["provider_headers"])
        assert resp.status_code == 422, body
    # Workers cannot report fields the control plane owns, such as reservations or reputation.
    beat = await client.post(
        "/api/v1/worker/heartbeat",
        json={"worker_version": "1", "metrics": {}, "deployments": [], "reserved_ram_mb": 0, "reputation_score": 100},
        headers=node["headers"],
    )
    assert beat.status_code == 422
    db.expire_all()
    assert (await db.get(Node, uuid.UUID(node["node_id"]))).owner_id != stranger


async def test_api_keys_cannot_claim_extra_scopes_or_owners(client, make_user):
    _, customer = await make_user("customer")
    for body in ({"name": "k", "scopes": ["admin"]}, {"name": "k", "user_id": str(uuid.uuid4())}):
        assert (await client.post("/api/v1/api-keys", json=body, headers=customer)).status_code == 422


# --- 17: SSRF ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reference",
    [
        "http://huggingface.co/a/b",
        "https://169.254.169.254/a/b",
        "https://localhost/a/b",
        "https://huggingface.co:8443/a/b",
        "https://huggingface.co.evil.example/a/b",
        "https://evil.example/huggingface.co/a/b",
        "https://user@127.0.0.1/a/b",
        "file:///etc/passwd",
    ],
)
def test_model_imports_only_reach_hugging_face(reference):
    with pytest.raises(HTTPException):
        huggingface.parse_reference(reference)


async def test_hugging_face_lookups_never_follow_redirects(monkeypatch):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data"})

    huggingface.set_transport(httpx.MockTransport(handler))
    try:
        with pytest.raises(HTTPException):
            await huggingface.fetch_repo(huggingface.parse_reference("acme/model"))
    finally:
        huggingface.set_transport(None)
    assert seen and all(url.startswith(settings.HUGGINGFACE_URL) for url in seen)


def test_sponsor_links_accept_https_only():
    from pydantic import ValidationError

    from app.services.sponsorship_service import CampaignIn

    base = {"name": "n1", "sponsor": "s1", "category": "ai_tools", "headline": "hello", "placements": ["landing"]}
    # The click redirect is followed by the viewer's browser, never fetched by the server.
    for url in ("http://x.example", "javascript:alert(1)", "data:text/html,x", "ftp://x.example/"):
        with pytest.raises(ValidationError):
            CampaignIn(**base, target_url=url)


# --- 18: production configuration -----------------------------------------------------------------------------

PROD = {
    "ENVIRONMENT": "production",
    "PUBLIC_BASE_URL": "https://api.example.com",
    "SECRET_KEY": "x" * 40,
    "MONGODB_URL": "mongodb+srv://u:p@cluster0.example.mongodb.net/",
    "CORS_ORIGINS": ["https://dashboard.example.com"],
    "_env_file": None,
}


def test_production_turns_debug_features_off():
    prod = Settings(**PROD)
    assert prod.api_docs_enabled is False and prod.test_credits_enabled is False and prod.is_dev is False
    assert Settings(**PROD, API_DOCS_ENABLED=True).api_docs_enabled is True  # explicit opt-in only
    for cors in (["*"], []):
        with pytest.raises(ValueError):
            Settings(**(PROD | {"CORS_ORIGINS": cors}))
    with pytest.raises(ValueError):
        Settings(**(PROD | {"PUBLIC_BASE_URL": "http://api.example.com"}))


def test_running_app_has_debug_off_and_no_wildcard_cors():
    from starlette.middleware.cors import CORSMiddleware

    from app.main import app

    assert app.debug is False
    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    assert "*" not in cors.kwargs["allow_origins"]


async def test_cors_answers_only_listed_origins(client):
    evil = await client.options(
        "/api/v1/auth/login", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert evil.headers.get("access-control-allow-origin") is None
    good = await client.options(
        "/api/v1/auth/login",
        headers={"Origin": settings.CORS_ORIGINS[0], "Access-Control-Request-Method": "POST"},
    )
    assert good.headers.get("access-control-allow-origin") == settings.CORS_ORIGINS[0]
