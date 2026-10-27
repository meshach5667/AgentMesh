"""Gemini API as the AI deployment agent's model (AI_PROVIDER=gemini).

Model calls still go through the inference queue (app.services.ai.inference_queue), so retries, expiry,
cancellation and the "answered only by the configured model" rule work exactly as with an Ollama machine. Here the
control plane itself answers queued requests by calling ``models/{GEMINI_MODEL}:generateContent``:

* right after a run asks (``answer_now``), so a planning conversation does not wait for the background loop;
* from the background monitor (``process_pending``), which picks up retries and anything left over.

The API key is sent in the ``x-goog-api-key`` header, never in the URL, so it cannot appear in request logs.
Replies are requested as JSON and then validated by app.services.ai.agent like any other model's: the model can only
choose among actions the application checks.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.core.database import session_scope
from app.core.logging import redact
from app.services.ai import inference_queue

logger = logging.getLogger(__name__)

PROVIDER_ID = "gemini"  # recorded as the "node" that answered a request
_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Tests replace the network with a fake Gemini."""
    global _transport
    _transport = transport


@dataclass
class Outcome:
    """The last call's result, for the health endpoint (per process)."""

    ok: bool | None = None
    at: float = 0.0
    error_code: str | None = None


last = Outcome()


class GeminiError(Exception):
    def __init__(self, code: str, message: str, retryable: bool):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable


@dataclass
class Reply:
    content: str
    prompt_tokens: int | None
    output_tokens: int | None
    model: str


def build_request(messages: list[dict], schema: dict) -> dict[str, Any]:
    """Translate a chat conversation into a generateContent body. System messages become the system instruction
    (with the output schema appended); assistant turns become "model" turns; consecutive turns of the same role are
    merged, because Gemini expects user and model turns to alternate."""
    system = [str(m["content"]) for m in messages if m.get("role") == "system"]
    system.append(
        "Reply with exactly one JSON object and nothing else. It must match this JSON schema:\n"
        + json.dumps(schema, separators=(",", ":"))
    )
    contents: list[dict[str, Any]] = []
    for m in messages:
        if m.get("role") == "system":
            continue
        role = "model" if m.get("role") == "assistant" else "user"
        part = {"text": str(m.get("content", ""))}
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].append(part)
        else:
            contents.append({"role": role, "parts": [part]})
    if not contents or contents[0]["role"] != "user":
        contents.insert(0, {"role": "user", "parts": [{"text": "Begin."}]})
    config: dict[str, Any] = {
        "temperature": 0,
        "maxOutputTokens": settings.AI_MAX_TOKENS,
        "responseMimeType": "application/json",
    }
    if settings.GEMINI_THINKING_BUDGET is not None:
        config["thinkingConfig"] = {"thinkingBudget": settings.GEMINI_THINKING_BUDGET}
    return {
        "systemInstruction": {"parts": [{"text": "\n\n".join(system)}]},
        "contents": contents,
        "generationConfig": config,
    }


def parse_response(data: dict[str, Any]) -> Reply:
    feedback = data.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        raise GeminiError("BLOCKED", f"Gemini blocked the request ({feedback['blockReason']})", retryable=False)
    candidates = data.get("candidates") or []
    if not candidates:
        raise GeminiError("EMPTY_REPLY", "Gemini returned no candidates", retryable=True)
    candidate = candidates[0]
    text = "".join(
        p.get("text", "")
        for p in (candidate.get("content") or {}).get("parts") or []
        if isinstance(p, dict) and not p.get("thought")
    )
    reason = candidate.get("finishReason")
    if reason not in (None, "STOP", "FINISH_REASON_UNSPECIFIED") or not text.strip():
        retryable = reason in ("MAX_TOKENS", "OTHER", None)
        raise GeminiError("BAD_FINISH", f"Gemini stopped early ({reason or 'no text'})", retryable=retryable)
    usage = data.get("usageMetadata") or {}
    return Reply(
        content=text,
        prompt_tokens=usage.get("promptTokenCount"),
        output_tokens=usage.get("candidatesTokenCount"),
        model=settings.GEMINI_MODEL,
    )


async def generate(messages: list[dict], schema: dict) -> Reply:
    if not settings.GEMINI_API_KEY:
        raise GeminiError("NOT_CONFIGURED", "GEMINI_API_KEY is not set", retryable=False)
    url = f"{settings.GEMINI_BASE_URL.rstrip('/')}/models/{settings.GEMINI_MODEL}:generateContent"
    headers = {"x-goog-api-key": settings.GEMINI_API_KEY, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(
            timeout=settings.GEMINI_TIMEOUT_SECONDS, transport=_transport, follow_redirects=False
        ) as client:
            resp = await client.post(url, json=build_request(messages, schema), headers=headers)
    except httpx.HTTPError as exc:
        raise GeminiError("NETWORK", f"Could not reach Gemini: {type(exc).__name__}", retryable=True) from None
    if resp.status_code != 200:
        try:
            detail = str((resp.json().get("error") or {}).get("message") or "")[:300]
        except ValueError:
            detail = ""
        retryable = resp.status_code in (408, 429) or resp.status_code >= 500
        detail = redact(detail.replace(settings.GEMINI_API_KEY, "[REDACTED]"))
        raise GeminiError(f"HTTP_{resp.status_code}", f"Gemini answered {resp.status_code}: {detail}", retryable)
    try:
        return parse_response(resp.json())
    except ValueError:
        raise GeminiError("BAD_JSON", "Gemini returned a non-JSON response", retryable=True) from None


async def _answer(request: Any) -> None:
    """Call Gemini for one leased request and record the outcome."""
    started = time.monotonic()
    payload = request.payload or {}
    try:
        reply = await generate(payload.get("messages") or [], payload.get("format") or {})
        fields: dict[str, Any] = {
            "content": reply.content,
            "error_code": None,
            "error": None,
            "retryable": False,
            "prompt_tokens": reply.prompt_tokens,
            "output_tokens": reply.output_tokens,
            "model": reply.model,
        }
        last.ok, last.error_code = True, None
    except GeminiError as exc:
        logger.warning("Gemini request %s failed: %s", request.id, redact(exc.message))
        fields = {
            "content": None,
            "error_code": exc.code,
            "error": exc.message,
            "retryable": exc.retryable,
            "prompt_tokens": None,
            "output_tokens": None,
            "model": None,
        }
        last.ok, last.error_code = False, exc.code
    last.at = time.time()
    async with session_scope() as db:
        await inference_queue.complete(
            db, PROVIDER_ID, request.id, latency_ms=int((time.monotonic() - started) * 1000), **fields
        )
        await db.commit()


async def process_pending(only: uuid.UUID | None = None) -> int:
    """Lease queued requests (all, or just ``only``) within AI_MAX_CONCURRENT_REQUESTS and answer them
    concurrently. Returns how many were answered (successfully or not)."""
    if settings.AI_PROVIDER != "gemini" or not settings.GEMINI_API_KEY:
        return 0
    async with session_scope() as db:
        leased = await inference_queue.lease_for_provider(db, PROVIDER_ID, settings.AI_MAX_CONCURRENT_REQUESTS, only)
    await asyncio.gather(*(_answer(r) for r in leased))
    return len(leased)


async def answer_now(request_id: uuid.UUID) -> bool:
    """Answer one request immediately (the run that asked waits for nothing). False if it was not leasable now
    (already answered, cancelled, or the concurrency limit is reached; the background loop retries)."""
    return await process_pending(only=request_id) > 0
