"""Privacy controls: retention, client deletion, and canary checks that prompts, outputs and credentials never reach
the logs, including on error paths (G-12, G-13)."""

import asyncio
import io
import json
import logging
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.logging import JsonFormatter, RedactingFilter
from app.core.timeutil import utcnow
from app.documents import (
    AiInferenceRequest,
    AiRun,
    AiRunEvent,
    AuditLog,
    Charge,
    Customer,
    DeploymentEvent,
    UsageRecord,
)
from app.services import retention_service
from app.services.tunnel import WorkerConnection, broker

CANARY_PROMPT = "CANARY-PROMPT-7f3a91"
CANARY_OUTPUT = "CANARY-OUTPUT-2b8c44"
CANARY_SECRET = "CANARY-SECRET-e51d0a"


# --- retention ------------------------------------------------------------------------------------------------


async def test_retention_purges_each_data_class_after_its_period(db):
    now = utcnow()
    old, recent = now - timedelta(days=4000), now - timedelta(hours=1)
    cust = uuid.uuid4()

    def run(status, created):
        return AiRun(
            customer_id=cust, user_id=uuid.uuid4(), status=status, request_text="x", limits={}, created_at=created
        )

    old_done, old_running, new_done = run("COMPLETED", old), run("DEPLOYING", old), run("FAILED", recent)
    db.add_all([old_done, old_running, new_done])
    db.add_all(
        [AiRunEvent(run_id=r.id, kind="info", message="m", created_at=r.created_at) for r in (old_done, new_done)]
    )
    answered_yesterday = AiInferenceRequest(
        run_id=new_done.id,
        purpose="planning",
        model="m",
        status="COMPLETED",
        result={"content": "out"},
        created_at=now - timedelta(hours=30),
        expires_at=now,
    )
    answered_now = AiInferenceRequest(
        run_id=new_done.id,
        purpose="planning",
        model="m",
        status="COMPLETED",
        result={"content": "out"},
        created_at=recent,
        expires_at=now,
    )
    db.add_all([answered_yesterday, answered_now])
    db.add_all([UsageRecord(deployment_id=uuid.uuid4(), created_at=t) for t in (old, recent)])
    db.add_all(
        [
            DeploymentEvent(deployment_id=uuid.uuid4(), to_status="READY", actor="system", created_at=t)
            for t in (old, recent)
        ]
    )
    db.add_all([AuditLog(action="x", created_at=t) for t in (old, recent)])
    charge = Charge(
        deployment_id=uuid.uuid4(),
        node_id=uuid.uuid4(),
        customer_wallet_id=uuid.uuid4(),
        provider_wallet_id=uuid.uuid4(),
        pricing_rule_id=uuid.uuid4(),
        resource_amount=Decimal(1),
        token_amount=Decimal(0),
        period_start=old,
        period_end=old,
        amount=Decimal(1),
        platform_fee=Decimal(0),
        provider_amount=Decimal(1),
        currency="NGN",
        created_at=old,
    )
    db.add(charge)
    await db.commit()

    counts = await retention_service.purge(db, now)

    assert counts["ai_runs"] == 1 and counts["ai_events"] == 1
    assert {r.id for r in await db.find(AiRun)} == {old_running.id, new_done.id}  # unfinished runs are kept
    db.expire_all()
    assert (await db.get(AiInferenceRequest, answered_yesterday.id)).result is None
    assert (await db.get(AiInferenceRequest, answered_now.id)).result == {"content": "out"}
    for doc in (UsageRecord, DeploymentEvent, AuditLog):
        assert await db.count(doc) == 1, doc.__name__
    assert await db.get(Charge, charge.id) is not None  # financial records are never purged here


async def test_retention_runs_in_the_background_monitor():
    import inspect

    from app.background import monitors

    assert "retention_service.run_retention" in inspect.getsource(monitors.monitor_loop)


async def test_customer_deletes_a_finished_ai_run_and_is_told_what_went(client, db, make_user):
    alice, alice_h = await make_user("customer")
    _, bob_h = await make_user("customer")
    customer = await db.find_one(Customer, {"user_id": alice.id})
    done = AiRun(customer_id=customer.id, user_id=alice.id, status="COMPLETED", request_text=CANARY_PROMPT, limits={})
    busy = AiRun(customer_id=customer.id, user_id=alice.id, status="DEPLOYING", request_text="y", limits={})
    db.add_all([done, busy, AiRunEvent(run_id=done.id, kind="info", message="m")])
    db.add(AiInferenceRequest(run_id=done.id, purpose="planning", model="m", status="COMPLETED", expires_at=utcnow()))
    await db.commit()

    assert (await client.delete(f"/api/v1/ai/deployments/{done.id}", headers=bob_h)).status_code == 404
    assert (await client.delete(f"/api/v1/ai/deployments/{busy.id}", headers=alice_h)).status_code == 409
    resp = await client.delete(f"/api/v1/ai/deployments/{done.id}", headers=alice_h)
    assert resp.status_code == 200
    assert resp.json()["deleted"] == {"inference_requests": 1, "events": 1, "runs": 1}
    assert "backups" in resp.json()["note"]
    db.expire_all()
    assert await db.get(AiRun, done.id) is None and await db.count(AiRunEvent) == 0
    assert (await db.find_one(AuditLog, {"action": "ai.run_deleted"})) is not None


# --- canaries: nothing private in the logs --------------------------------------------------------------------


@pytest.fixture
def production_log():
    """Capture every log record exactly as production writes it (JSON lines, redaction filter), at DEBUG."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    yield stream
    root.removeHandler(handler)
    root.setLevel(previous)


class CanaryWorker:
    """A node that answers with the output canary, or fails mid-stream with it in the error message."""

    def __init__(self, node_id, mode="ok"):
        self.mode = mode
        self.conn = WorkerConnection(node_id=uuid.UUID(str(node_id)), send_json=self._on_send, close=self._close)

    async def _close(self):
        pass

    async def _on_send(self, frame):
        if frame.get("type") == "request":
            asyncio.get_running_loop().create_task(self._respond(frame["id"]))

    async def _respond(self, rid):
        d = self.conn.dispatch
        d({"type": "response_start", "id": rid, "status": 200, "content_type": "application/x-ndjson"})
        if self.mode == "error":
            d({"type": "error", "id": rid, "code": "runtime_error", "message": f"runtime crashed on {CANARY_OUTPUT}"})
            return
        line = {
            "message": {"role": "assistant", "content": CANARY_OUTPUT},
            "done": True,
            "prompt_eval_count": 3,
            "eval_count": 2,
        }
        d({"type": "chunk", "id": rid, "data": json.dumps(line) + "\n"})
        d({"type": "response_end", "id": rid})


@pytest.fixture
async def serving(client, make_user, enroll_node, ollama_model):
    node = await enroll_node()
    _, customer = await make_user("customer")
    dep = (await client.post("/api/v1/deployments", json={"model_id": str(ollama_model.id)}, headers=customer)).json()
    await client.post(
        f"/api/v1/worker/deployments/{dep['id']}/status", json={"state": "READY"}, headers=node["headers"]
    )
    key = (await client.post("/api/v1/api-keys", json={"name": "k"}, headers=customer)).json()["key"]
    yield {"dep": dep, "node": node, "key": key, "customer": customer}


async def _chat(client, serving, worker, **extra):
    await broker.register(worker.conn)
    try:
        return await client.post(
            f"/api/v1/deployments/{serving['dep']['id']}/ollama/api/chat",
            json={"messages": [{"role": "user", "content": CANARY_PROMPT}], "stream": False, **extra},
            headers={"Authorization": f"Bearer {serving['key']}"},
        )
    finally:
        broker.unregister(worker.conn)


def _assert_clean(log: io.StringIO, *secrets: str):
    text = log.getvalue()
    assert text, "nothing was captured; the canary check would be meaningless"
    for secret in secrets:
        assert secret not in text, f"{secret} leaked into the logs"


async def test_prompts_outputs_and_keys_stay_out_of_logs_on_success(client, serving, production_log):
    resp = await _chat(client, serving, CanaryWorker(serving["node"]["node_id"]))
    assert resp.status_code == 200 and CANARY_OUTPUT in resp.text
    _assert_clean(production_log, CANARY_PROMPT, CANARY_OUTPUT, serving["key"], serving["node"]["credential"])


async def test_prompts_and_outputs_stay_out_of_logs_when_the_runtime_fails(client, serving, production_log):
    await _chat(client, serving, CanaryWorker(serving["node"]["node_id"], mode="error"))
    _assert_clean(production_log, CANARY_PROMPT, CANARY_OUTPUT, serving["key"])


async def test_prompts_stay_out_of_logs_when_the_gateway_itself_crashes(client, serving, production_log, monkeypatch):
    async def explode(node_id, frame):
        raise RuntimeError(f"unexpected failure while handling {frame}")

    monkeypatch.setattr(broker, "open_request", explode)
    with pytest.raises(RuntimeError):
        await _chat(client, serving, CanaryWorker(serving["node"]["node_id"]))
    _assert_clean(production_log, CANARY_PROMPT, serving["key"])


async def test_malformed_bodies_and_credentials_stay_out_of_logs(client, serving, production_log, make_user):
    url = f"/api/v1/deployments/{serving['dep']['id']}/ollama/api/chat"
    headers = {"Authorization": f"Bearer {serving['key']}", "Content-Type": "application/json"}
    await client.post(url, content=f'{{"messages": "{CANARY_PROMPT}" broken', headers=headers)
    await client.post(url, json={"messages": []}, headers={"Authorization": f"Bearer am_sk_{CANARY_SECRET}"})
    await client.post("/api/v1/auth/login", json={"email": "who@example.com", "password": CANARY_SECRET})
    await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {CANARY_SECRET}.x.y"})
    _assert_clean(production_log, CANARY_PROMPT, CANARY_SECRET, serving["key"])


async def test_security_events_drop_fields_outside_the_allowlist(production_log):
    from app.core import security_events

    security_events.emit("node.session_refused", node_id="n1", prompt=CANARY_PROMPT, token=CANARY_SECRET)
    text = production_log.getvalue()
    assert "node.session_refused" in text and "node_id=n1" in text
    _assert_clean(production_log, CANARY_PROMPT, CANARY_SECRET)
