"""AI deployment agent on the Gemini API (AI_PROVIDER=gemini), against a fake Gemini that checks every request.

No real Gemini call is made here. The fake enforces what the real API needs: the key in the x-goog-api-key header
(never the URL), alternating user/model turns, a JSON response type, and the configured model.
"""

import io
import json
import logging
import uuid

import httpx
import pytest

from app.core.config import settings
from app.core.logging import JsonFormatter, RedactingFilter
from app.documents import AiInferenceRequest
from app.services.ai import gemini, inference_queue, workflow
from tests.test_ai_agent import LIMITS, ProbeWorker, events, final_plan, mid, report, run_of, start

KEY = "AIza" + "S" * 35
MODEL = "gemini-2.5-flash"


class FakeGemini:
    """Answers generateContent with scripted replies: a dict/str becomes the model's JSON text; an int is an HTTP
    error status; a full dict under "raw" is returned as the response body."""

    def __init__(self):
        self.replies: list = []
        self.requests: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append({"url": str(request.url), "headers": dict(request.headers), "body": body})
        assert request.headers.get("x-goog-api-key") == KEY
        assert KEY not in str(request.url)
        assert str(request.url).endswith(f"/models/{MODEL}:generateContent")
        roles = [c["role"] for c in body["contents"]]
        assert roles[0] == "user" and all(a != b for a, b in zip(roles, roles[1:], strict=False)), roles
        reply = self.replies.pop(0) if self.replies else {"action": "final_plan"}
        if isinstance(reply, int):
            return httpx.Response(reply, json={"error": {"message": f"failure {reply} for key {KEY}"}})
        if isinstance(reply, dict) and "raw" in reply:
            return httpx.Response(200, json=reply["raw"])
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 420, "candidatesTokenCount": 37},
                "modelVersion": MODEL,
            },
        )


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", KEY)
    monkeypatch.setattr(settings, "GEMINI_MODEL", MODEL)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_PER_MINUTE", 100)
    monkeypatch.setattr(gemini, "last", gemini.Outcome())
    g = FakeGemini()
    gemini.set_transport(httpx.MockTransport(g.handler))
    yield g
    gemini.set_transport(None)


@pytest.fixture
async def connected(enroll_node):
    from app.services.tunnel import broker

    node = await enroll_node(cpu=4, ram_mb=8192, disk_mb=20000)
    worker = ProbeWorker(node["node_id"])
    await broker.register(worker.conn)
    yield node, worker
    broker.unregister(worker.conn)


def tool_call(model):
    return {
        "action": "call_tool",
        "tool": "inspect_model_requirements",
        "arguments": {"model_id": mid(model)},
        "explanation": "check requirements",
    }


async def test_gemini_plans_deploys_verifies_and_publishes(client, db, make_user, connected, ollama_model, fake):
    node, worker = connected
    fake.replies = [tool_call(ollama_model), final_plan(ollama_model)]
    _, customer = await make_user("customer")
    run = (await start(client, customer)).json()

    # The control plane answered both model turns itself, right away: no background pass was needed.
    got = (await client.get(f"/api/v1/ai/deployments/{run['id']}", headers=customer)).json()
    assert got["status"] == "DEPLOYING", got
    assert got["agent_steps"] == 2 and got["tool_calls"] == 1 and got["explanation"] == "Smallest fit."
    assert len(fake.requests) == 2

    first, second = fake.requests[0]["body"], fake.requests[1]["body"]
    system = first["systemInstruction"]["parts"][0]["text"]
    assert "JSON schema" in system and '"action"' in system
    assert first["generationConfig"] == {
        "temperature": 0,
        "maxOutputTokens": settings.AI_MAX_TOKENS,
        "responseMimeType": "application/json",
        "thinkingConfig": {"thinkingBudget": 0},
    }
    assert "Deploy a small chat model" in first["contents"][0]["parts"][0]["text"]
    assert [c["role"] for c in second["contents"]] == ["user", "model", "user"]
    assert "TOOL RESULT for inspect_model_requirements" in second["contents"][-1]["parts"][0]["text"]

    rows = await db.find(AiInferenceRequest)
    assert all(r.model == MODEL and r.node_id == "gemini" and r.status == "COMPLETED" for r in rows)
    assert all(r.payload is None and r.result["prompt_tokens"] == 420 for r in rows)

    await report(client, node, got["deployment_id"], "READY")
    assert await workflow.advance(uuid.UUID(run["id"])) == "READY"
    assert worker.frames[-1]["path"] == "/v1/chat/completions"


async def test_transient_gemini_errors_are_retried_then_succeed(
    client, db, make_user, connected, ollama_model, fake, monkeypatch
):
    monkeypatch.setattr(settings, "AI_MAX_ATTEMPTS", 3)
    fake.replies = [503, 429, final_plan(ollama_model)]
    _, customer = await make_user("customer")
    run = (await start(client, customer)).json()
    assert (await run_of(db, run["id"])).status == "PLANNING"  # first attempt failed, request re-queued
    health = (await client.get("/api/v1/ai/health", headers=customer)).json()
    assert health["status"] == "degraded" and health["model"] == MODEL

    await workflow.run_due()  # background pass: retry (429), still pending
    await workflow.run_due()  # retry succeeds and the run moves on
    assert (await run_of(db, run["id"])).status in ("SUBMITTING", "DEPLOYING")
    assert len(fake.requests) == 3
    assert (await client.get("/api/v1/ai/health", headers=customer)).json()["status"] == "available"


async def test_permanent_gemini_error_fails_the_run_and_never_logs_the_key(
    client, db, make_user, ollama_model, fake, monkeypatch
):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(JsonFormatter())
    logging.getLogger().addHandler(handler)
    try:
        fake.replies = [400]
        _, customer = await make_user("customer")
        run = (await start(client, customer)).json()
        await workflow.run_due()
    finally:
        logging.getLogger().removeHandler(handler)
    final = await run_of(db, run["id"])
    assert final.status == "FAILED" and final.error_code == "AI_ERROR"
    req = await db.find_one(AiInferenceRequest)
    assert req.error_code == "HTTP_400" and KEY not in (req.error or "")
    assert "Gemini answered 400" in stream.getvalue() and KEY not in stream.getvalue()


async def test_invalid_reply_gets_a_correction_and_the_next_answer_counts(client, db, make_user, ollama_model, fake):
    fake.replies = ["this is not json", final_plan(ollama_model)]
    _, customer = await make_user("customer")
    run = (await start(client, customer)).json()
    if (await run_of(db, run["id"])).status == "PLANNING":
        await workflow.run_due()
    assert (await run_of(db, run["id"])).status in ("SUBMITTING", "DEPLOYING")
    assert any("invalid" in e.message for e in await events(db, run["id"]))
    corrected = fake.requests[1]["body"]["contents"][-1]["parts"][-1]["text"]
    assert "not valid" in corrected.lower() or "invalid" in corrected.lower() or "json" in corrected.lower()


@pytest.mark.parametrize(
    ("raw", "code", "retried"),
    [
        ({"candidates": [{"content": {"parts": [{"text": ""}]}, "finishReason": "MAX_TOKENS"}]}, "BAD_FINISH", True),
        ({"candidates": [{"content": {"parts": [{"text": "{}"}]}, "finishReason": "SAFETY"}]}, "BAD_FINISH", False),
        ({"promptFeedback": {"blockReason": "SAFETY"}}, "BLOCKED", False),
        ({"candidates": []}, "EMPTY_REPLY", True),
    ],
)
async def test_unusable_gemini_answers_are_classified(make_user, db, raw, code, retried, fake):
    from app.core.database import session_scope

    fake.replies = [{"raw": raw}]
    async with session_scope() as s:
        req = await inference_queue.enqueue(s, run_id=None, purpose="planning", messages=[], schema={})
        await s.commit()
    assert await gemini.answer_now(req.id)
    db.expire_all()
    row = await db.get(AiInferenceRequest, req.id)
    assert row.error_code == code
    assert row.status == ("PENDING" if retried else "FAILED")


async def test_not_configured_without_a_key(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    _, customer = await make_user("customer")
    assert (await client.get("/api/v1/ai/health", headers=customer)).json()["status"] == "not_configured"
    resp = await start(client, customer)
    assert resp.status_code == 503 and resp.json()["detail"]["code"] == "ai_not_configured"


async def test_inference_machines_get_no_work_while_gemini_answers(client, db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "AI_INFERENCE_TOKEN", "t" * 40)
    headers = {"Authorization": "Bearer " + "t" * 40, "X-AgentMesh-Inference-Node": "hp15"}
    beat = await client.post(
        "/api/v1/ai/inference/heartbeat",
        json={"model": MODEL, "ollama_ok": True, "model_ready": True, "accepting": True},
        headers=headers,
    )
    assert beat.status_code == 200 and beat.json()["accepted"] is False and beat.json()["provider"] == "gemini"
    leased = await client.post(
        "/api/v1/ai/inference/lease", json={"max_requests": 1, "wait_seconds": 0}, headers=headers
    )
    assert leased.json() == []


def test_request_translation_merges_turns_and_keeps_system_text_out_of_contents():
    body = gemini.build_request(
        [
            {"role": "system", "content": "You plan deployments."},
            {"role": "assistant", "content": "earlier reply"},
            {"role": "user", "content": "a"},
            {"role": "user", "content": "b"},
        ],
        {"type": "object"},
    )
    assert body["systemInstruction"]["parts"][0]["text"].startswith("You plan deployments.")
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    assert [p["text"] for p in body["contents"][2]["parts"]] == ["a", "b"]


def test_thinking_config_can_be_left_to_the_model(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_THINKING_BUDGET", None)
    assert "thinkingConfig" not in gemini.build_request([{"role": "user", "content": "x"}], {})["generationConfig"]


def test_gemini_settings_are_validated():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError, match="AI_PROVIDER"):
        Settings(AI_PROVIDER="openai", ENVIRONMENT="test", _env_file=None)
    assert Settings(AI_PROVIDER="ollama", ENVIRONMENT="test", _env_file=None).ai_model == settings.OLLAMA_MODEL
    assert Settings(ENVIRONMENT="test", _env_file=None).AI_PROVIDER == "gemini"


def test_google_api_keys_are_redacted_from_logs():
    from app.core.logging import redact

    assert KEY not in redact(f"calling with key={KEY} and header {KEY}")


_ = LIMITS  # shared limits are used through start()
