"""Deployment configuration that the control plane's security depends on (G-02, G-03, G-23)."""

from pathlib import Path

import httpx
import pytest
import yaml
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.ratelimit import limiters

ROOT = Path(__file__).resolve().parents[2]


def _compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text())


def test_compose_does_not_expose_redis_or_mongo_and_requires_a_redis_password():
    services = _compose()["services"]
    for name in ("redis", "mongo"):
        assert "ports" not in services[name], f"{name} must not be published on the host"
    assert "--requirepass" in services["redis"]["command"]
    api_env = "\n".join(services["api"]["environment"])
    assert "REDIS_URL=redis://:${REDIS_PASSWORD}@" in api_env


def test_compose_and_image_never_trust_forwarded_headers_from_everyone():
    services = _compose()["services"]
    api = services["api"]
    assert "command" not in api or "forwarded-allow-ips='*'" not in str(api["command"])
    assert any(e.startswith("FORWARDED_ALLOW_IPS=${FORWARDED_ALLOW_IPS:?") for e in api["environment"])
    assert all(p.startswith("127.0.0.1:") for p in api["ports"] + services["client"]["ports"])
    dockerfile = (ROOT / "Dockerfile.server").read_text()
    assert "ENV FORWARDED_ALLOW_IPS=127.0.0.1" in dockerfile
    assert '"--proxy-headers"' in dockerfile and '"--ws-max-size", "2097152"' in dockerfile


@pytest.mark.parametrize(
    ("peer", "trusted", "expected"),
    [
        ("203.0.113.9", "10.0.0.0/8", "203.0.113.9"),  # direct caller: a spoofed X-Forwarded-For is ignored
        ("10.1.2.3", "10.0.0.0/8", "198.51.100.7"),  # the trusted proxy: its X-Forwarded-For is used
    ],
)
async def test_login_throttle_keys_on_the_real_client_address(mongo, peer, trusted, expected, monkeypatch):
    from app.main import app

    seen: list[str] = []
    real_allow = limiters.requests.allow

    async def spy(key, limit):
        if key.startswith("auth:ip:"):
            seen.append(key.removeprefix("auth:ip:"))
        return await real_allow(key, limit)

    monkeypatch.setattr(limiters.requests, "allow", spy)
    wrapped = ProxyHeadersMiddleware(app, trusted_hosts=trusted)
    transport = httpx.ASGITransport(app=wrapped, client=(peer, 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong-password"},
            headers={"X-Forwarded-For": "198.51.100.7"},
        )
    assert seen == [expected]
