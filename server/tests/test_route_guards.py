"""Every route is either deliberately public or guarded, and guarded routes refuse anonymous callers.

The static test walks every registered route: a new route that is neither listed here as public nor depends on an
authentication dependency fails it, so forgetting a guard cannot slip through review. The dynamic test then calls
every non-public route without credentials (and with a forged token) and expects a refusal.
"""

import uuid

import pytest
from fastapi.routing import APIRoute, APIWebSocketRoute, iter_route_contexts

from app.core.security import ALGORITHM
from app.main import app

# Intentionally anonymous, with the reason.
PUBLIC = {
    ("POST", "/api/v1/auth/login"): "sign-in",
    ("POST", "/api/v1/auth/register"): "self-service sign-up (customer/provider only)",
    ("POST", "/api/v1/auth/refresh"): "authenticated by the single-use refresh token in its body",
    ("GET", "/api/v1/billing/pricing"): "published price list",
    ("GET", "/api/v1/marketplace/nodes"): "public capacity listing",
    ("GET", "/api/v1/marketplace/pricing"): "public price summary",
    ("GET", "/api/v1/models"): "public model catalog",
    ("GET", "/api/v1/models/{id}"): "public model catalog",
    ("GET", "/api/v1/payments/config"): "whether payments are enabled (no secrets)",
    ("GET", "/api/v1/sponsored"): "sponsored slot contents (no personal data)",
    ("POST", "/api/v1/sponsored/{campaign_id}/impression"): "signed view token in the body",
    ("GET", "/api/v1/sponsored/{campaign_id}/click"): "signed view token in the query",
    ("GET", "/api/v1/stats/public"): "aggregate network figures",
    ("POST", "/api/v1/worker/enroll"): "authenticated by the one-time enrollment token in its body",
    ("GET", "/health"): "liveness",
    ("GET", "/health/ready"): "readiness",
}

# Routes that authenticate inside the handler instead of through a dependency, so the static check cannot see it.
SELF_AUTHENTICATING = {
    ("GET", "/api/v1/deployments/{deployment_id}/ollama/{path:path}"): "API key or user token",
    ("POST", "/api/v1/deployments/{deployment_id}/ollama/{path:path}"): "API key or user token",
    ("GET", "/api/v1/deployments/{deployment_id}/v1/{path:path}"): "API key or user token",
    ("POST", "/api/v1/deployments/{deployment_id}/v1/{path:path}"): "API key or user token",
    ("POST", "/api/v1/payments/paystack/webhook"): "Paystack HMAC signature",
    ("GET", "/metrics"): "METRICS_TOKEN",
    ("POST", "/api/v1/nodes/{id}/heartbeat"): "legacy node API key",
    ("WS", "/api/v1/worker/tunnel"): "node credential",
}

GUARDS = {"get_current_user", "current_node", "inference_node"}


def _routes():
    for ctx in iter_route_contexts(app.routes):
        route = ctx.original_route
        if isinstance(route, APIWebSocketRoute):
            yield "WS", ctx.path or route.path, route
        elif isinstance(route, APIRoute):
            for method in sorted(ctx.methods or route.methods):
                yield method, ctx.path, route


def _dependency_names(dependant, acc=None) -> set[str]:
    acc = set() if acc is None else acc
    for sub in dependant.dependencies:
        acc.add(getattr(sub.call, "__name__", ""))
        _dependency_names(sub, acc)
    return acc


def _ws_path(route) -> str:
    return "/api/v1/worker/tunnel" if route.path.endswith("/tunnel") else route.path


def test_every_route_is_public_by_decision_or_guarded():
    seen: set[tuple[str, str]] = set()
    unguarded = []
    for method, path, route in _routes():
        key = (method, _ws_path(route) if method == "WS" else path)
        seen.add(key)
        if key in PUBLIC or key in SELF_AUTHENTICATING:
            continue
        if not GUARDS & _dependency_names(route.dependant):
            unguarded.append(key)
    assert unguarded == [], f"Routes without an authentication guard (add one, or list them as public): {unguarded}"
    stale = (set(PUBLIC) | set(SELF_AUTHENTICATING)) - seen
    assert not stale, f"Listed routes that no longer exist: {stale}"


def _protected_http_routes():
    for method, path, _route in _routes():
        if method in ("WS", "HEAD") or (method, path) in PUBLIC:
            continue
        yield method, path


def _concrete(path: str) -> str:
    out, rest = "", path
    while "{" in rest:
        head, tail = rest.split("{", 1)
        name, rest = tail.split("}", 1)
        value = {
            "path:path": "v1/chat/completions",
            "name": "agentmesh_worker-1.0-py3-none-any.whl",
            "reference": "ref-1",
        }.get(name, str(uuid.uuid4()))
        out += head + value
    return out + rest


def _forged_token() -> str:
    import jwt

    return jwt.encode({"sub": str(uuid.uuid4()), "exp": 4102444800}, "not-the-server-key-" * 3, algorithm=ALGORITHM)


@pytest.mark.parametrize(("method", "path"), sorted(_protected_http_routes()))
@pytest.mark.parametrize("credential", ["none", "forged"])
async def test_anonymous_and_forged_callers_are_refused(client, monkeypatch, method, path, credential):
    from app.core.config import settings

    monkeypatch.setattr(settings, "METRICS_TOKEN", "m" * 40)
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_" + "k" * 32)  # so the webhook checks signatures
    headers = {} if credential == "none" else {"Authorization": f"Bearer {_forged_token()}"}
    if path.startswith("/api/v1/worker/"):
        headers["X-AgentMesh-Node-Id"] = str(uuid.uuid4())
    resp = await client.request(method, _concrete(path), headers=headers, json={})
    assert resp.status_code in (401, 403), f"{method} {path} -> {resp.status_code}: {resp.text[:200]}"


class FakeWebSocket:
    """Just enough of a WebSocket to drive the tunnel endpoint's handshake."""

    def __init__(self, headers: dict[str, str]):
        self.headers = headers
        self.accepted = False
        self.close_code: int | None = None

    async def accept(self):
        self.accepted = True

    async def close(self, code: int = 1000):
        self.close_code = code


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"x-agentmesh-node-id": str(uuid.uuid4())},
        {"x-agentmesh-node-id": str(uuid.uuid4()), "authorization": "Bearer am_node_forged"},
        {"x-agentmesh-node-id": "not-a-uuid", "authorization": "Bearer am_node_forged"},
    ],
)
async def test_worker_tunnel_refuses_unauthenticated_connections(mongo, headers):
    from app.api.v1.worker import tunnel

    ws = FakeWebSocket(headers)
    await tunnel(ws)  # type: ignore[arg-type]
    assert ws.accepted is False and ws.close_code == 4401
