"""Shared test fixtures.

Database-backed tests run against MongoDB (see tests/mongo_support.py): TEST_MONGODB_URL when set (CI), otherwise a
private single-node replica set started from the local mongod. Each test gets a fresh database.
"""

import os
import uuid

os.environ["ENVIRONMENT"] = "test"
os.environ["PAYSTACK_SECRET_KEY"] = ""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.ratelimit import limiters
from app.core.security import create_access_token, get_password_hash
from app.documents import Customer, Model, ModelArtifact, Provider, User
from app.main import app
from app.services import auth_service

pytest_plugins = ["tests.mongo_support"]


@pytest.fixture
async def db(mdb):
    """A Session on the test database, like the one request handlers get."""
    return mdb


@pytest.fixture(autouse=True)
def _isolate_state():
    """Reset in-process limiters between tests."""
    limiters.use_memory()


@pytest.fixture
async def client(mongo):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    """A syntactically valid token for a user that does not exist."""
    token = create_access_token(str(uuid.uuid4()), str(uuid.uuid4()))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_user(db):
    """Create a user with the given role (and matching profile) and return (user, auth headers)."""

    async def _make(role: str, *, is_active: bool = True):
        user = User(
            email=f"{role}-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("correct-horse-battery"),
            role=role,
            is_active=is_active,
        )
        db.add(user)
        await db.flush()
        if role == "provider":
            db.add(Provider(user_id=user.id))
        elif role == "customer":
            db.add(Customer(user_id=user.id))
        # Staff fixtures stand for operators who completed MFA; tests/test_auth_security.py covers the MFA flow.
        tokens = await auth_service.start_session(db, user, mfa_verified=role in ("operator", "admin"))
        await db.commit()
        return user, {"Authorization": f"Bearer {tokens['access_token']}"}

    return _make


@pytest.fixture
async def approved_model(db):
    model = Model(name="llama3.2:1b", version="1", runtime="ollama", source="ollama", is_approved=True)
    db.add(model)
    await db.commit()
    return model


# --- Phase 2 helpers -----------------------------------------------------------------------------------

HARDWARE = {
    "os": "Linux",
    "arch": "x86_64",
    "cpu_model": "Test CPU",
    "cpu_cores": 8,
    "ram_mb": 16384,
    "disk_free_mb": 100000,
    "gpus": [],
}


def worker_headers(node: dict) -> dict:
    return {
        "Authorization": f"Bearer {node['credential']}",
        "X-AgentMesh-Node-Id": str(node["node_id"]),
        "X-AgentMesh-Protocol": "1",
    }


@pytest.fixture
def enroll_node(client, make_user):
    """Enroll a worker through the real API. Returns {node_id, credential, headers, provider_headers}."""

    async def _enroll(
        *, cpu=4, ram_mb=4096, disk_mb=10000, vram_mb=0, hardware=None, provider=None, region=None, runtimes=None
    ):
        if provider is None:
            _, provider = await make_user("provider")
        tok = await client.post("/api/v1/nodes/enrollment-tokens", json={"region": region}, headers=provider)
        assert tok.status_code == 201, tok.text
        resp = await client.post(
            "/api/v1/worker/enroll",
            json={
                "token": tok.json()["token"],
                "name": "test-node",
                "mode": "docker",
                "worker_version": "test",
                "protocol_version": 1,
                "hardware": hardware or HARDWARE,
                "allocation": {"cpu_cores": cpu, "ram_mb": ram_mb, "disk_mb": disk_mb, "vram_mb": vram_mb},
                "runtimes": runtimes
                if runtimes is not None
                else [{"name": "ollama", "version": "0.0.0", "backend": "docker", "available": True}],
            },
        )
        assert resp.status_code == 200, resp.text
        node = {"node_id": resp.json()["node_id"], "credential": resp.json()["node_credential"]}
        node["headers"] = worker_headers(node)
        node["provider_headers"] = provider
        return node

    return _enroll


@pytest.fixture
async def ollama_model(db):
    model = Model(
        name="Qwen2.5 0.5B",
        version="0.5b",
        runtime="ollama",
        source="ollama-registry",
        model_tag="qwen2.5:0.5b",
        min_ram_mb=1024,
        min_disk_mb=768,
        min_cpu_cores=1,
        is_approved=True,
    )
    db.add(model)
    await db.flush()
    db.add(
        ModelArtifact(
            model_id=model.id,
            runtime="ollama",
            source_type="ollama",
            reference="qwen2.5:0.5b",
            format="ollama",
            min_ram_mb=1024,
            min_disk_mb=768,
            min_cpu_cores=1,
        )
    )
    await db.commit()
    await db.refresh(model)
    return model
