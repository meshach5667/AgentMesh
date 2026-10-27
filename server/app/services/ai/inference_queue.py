"""Queue of model calls made by the AI deployment agent.

Every model call is stored here first and answered by the Gemini API (app.services.ai.gemini), so retries, expiry and
cancellation do not depend on a single HTTP call succeeding. Requests wait (bounded by AI_QUEUE_MAX_LENGTH) until
answered or until they expire after AI_QUEUE_TTL_SECONDS. A lease that is not answered within AI_REQUEST_TIMEOUT is
handed out again, at most AI_MAX_ATTEMPTS times. A request is never answered by a model other than GEMINI_MODEL.
"""

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.core.config import settings
from app.core.database import Session
from app.core.logging import redact
from app.core.timeutil import utcnow
from app.documents.ai import AiInferenceRequest

OPEN = ["PENDING", "LEASED"]
MAX_RESULT_CHARS = 16_000


class QueueFull(Exception):  # noqa: N818
    pass


async def depth(db: Session) -> int:
    return await db.count(AiInferenceRequest, {"status": {"$in": OPEN}})


async def enqueue(
    db: Session, *, run_id: uuid.UUID | None, purpose: str, messages: list[dict], schema: dict
) -> AiInferenceRequest:
    """Queue one model call. Raises QueueFull when the queue is at its limit. Does not commit."""
    if await depth(db) >= settings.AI_QUEUE_MAX_LENGTH:
        raise QueueFull("The AI service queue is full")
    now = utcnow()
    req = AiInferenceRequest(
        id=uuid.uuid4(),
        run_id=run_id,
        purpose=purpose,
        model=settings.GEMINI_MODEL,
        payload={"messages": messages, "format": schema},
        status="PENDING",
        max_attempts=settings.AI_MAX_ATTEMPTS,
        created_at=now,
        expires_at=now + timedelta(seconds=settings.AI_QUEUE_TTL_SECONDS),
    )
    db.add(req)
    await db.flush()
    return req


async def cancel(db: Session, request_id: uuid.UUID | None) -> None:
    if request_id is None:
        return
    await db.update_one(
        AiInferenceRequest,
        {"_id": request_id, "status": {"$in": OPEN}},
        {"$set": {"status": "CANCELLED", "payload": None, "completed_at": utcnow()}},
    )


# --- Health ---------------------------------------------------------------------------------------------

# After a failed Gemini call the service reports "degraded" for this long (or until a call succeeds).
DEGRADED_SECONDS = 180


@dataclass
class Health:
    status: str  # available | degraded | not_configured
    model: str
    queue_depth: int
    message: str

    @property
    def available(self) -> bool:
        return self.status == "available"


async def health(db: Session) -> Health:
    from app.services.ai import gemini

    queued = await depth(db)
    model = settings.GEMINI_MODEL
    if not settings.GEMINI_API_KEY:
        return Health("not_configured", model, queued, "The AI service is not configured.")
    if gemini.last.ok is False and time.time() - gemini.last.at <= DEGRADED_SECONDS:
        msg = "The AI service is having trouble answering; requests are retried automatically."
        return Health("degraded", model, queued, msg)
    return Health("available", model, queued, "The AI service is available.")


# --- Leases --------------------------------------------------------------------------------------------


async def lease_for_provider(
    db: Session, provider_id: str, max_requests: int, only: uuid.UUID | None = None
) -> list[AiInferenceRequest]:
    """Lease queued requests to ``provider_id`` (one Gemini batch), within the global AI_MAX_CONCURRENT_REQUESTS
    limit. ``only`` restricts it to one request. Commits."""
    now = utcnow()
    in_flight = await db.count(AiInferenceRequest, {"status": "LEASED", "lease_expires_at": {"$gte": now}})
    room = min(max_requests, settings.AI_MAX_CONCURRENT_REQUESTS - in_flight)
    if room <= 0:
        return []
    query: dict[str, Any] = {"status": "PENDING", "expires_at": {"$gt": now}, "model": settings.GEMINI_MODEL}
    if only is not None:
        query["_id"] = only
    candidates = await db.find(AiInferenceRequest, query, sort=[("created_at", 1)], limit=room)
    leased = []
    for req in candidates:
        claimed = await db.update_one(
            AiInferenceRequest,
            {"_id": req.id, "status": "PENDING"},
            {
                "$set": {
                    "status": "LEASED",
                    "attempts": req.attempts + 1,
                    "node_id": provider_id,
                    "lease_expires_at": now + timedelta(seconds=settings.AI_REQUEST_TIMEOUT),
                }
            },
        )
        if claimed:
            req.status, req.attempts, req.node_id = "LEASED", req.attempts + 1, provider_id
            req.lease_expires_at = now + timedelta(seconds=settings.AI_REQUEST_TIMEOUT)
            leased.append(req)
    await db.commit()
    return leased


async def complete(
    db: Session,
    node_id: str,
    request_id: uuid.UUID,
    *,
    content: str | None,
    error_code: str | None,
    error: str | None,
    retryable: bool,
    latency_ms: int | None,
    prompt_tokens: int | None,
    output_tokens: int | None,
    model: str | None,
) -> AiInferenceRequest | None:
    """Record the answer to a leased request. Returns None if the lease is no longer ``node_id``'s (expired and
    re-leased, cancelled): such late answers are discarded. Does not commit."""
    req = await db.get(AiInferenceRequest, request_id)
    if req is None or req.status != "LEASED" or req.node_id != node_id:
        return None
    now = utcnow()
    values: dict[str, Any] = {"latency_ms": latency_ms, "lease_expires_at": None}
    if content is not None and error_code is None:
        if model != req.model:
            error_code, error, retryable = "MODEL_MISMATCH", f"answered by {model}, expected {req.model}", False
        else:
            values.update(
                status="COMPLETED",
                result={
                    "content": content[:MAX_RESULT_CHARS],
                    "prompt_tokens": prompt_tokens,
                    "output_tokens": output_tokens,
                },
                payload=None,
                completed_at=now,
            )
    if "status" not in values:
        if retryable and req.attempts < req.max_attempts and req.expires_at > now:
            values.update(status="PENDING", node_id=None)
        else:
            values.update(status="FAILED", payload=None, completed_at=now)
        values.update(error_code=(error_code or "INFERENCE_ERROR")[:50], error=redact(error or "")[:500])
    if not await db.update_one(
        AiInferenceRequest, {"_id": req.id, "status": "LEASED", "node_id": node_id}, {"$set": values}
    ):
        return None
    for key, value in values.items():
        setattr(req, key, value)
    return req


async def expire(db: Session, now: datetime | None = None) -> set[uuid.UUID]:
    """Expire requests that waited too long and re-queue (or fail) unanswered leases. Returns the runs
    affected. Does not commit."""
    now = now or utcnow()
    runs: set[uuid.UUID] = set()
    stale = await db.find(AiInferenceRequest, {"status": "LEASED", "lease_expires_at": {"$lt": now}})
    for req in stale:
        retry = req.attempts < req.max_attempts and req.expires_at > now
        values: dict[str, Any] = (
            {"status": "PENDING", "node_id": None, "lease_expires_at": None}
            if retry
            else {"status": "FAILED", "payload": None, "completed_at": now}
        )
        values.update(error_code="TIMEOUT", error="The AI service did not answer in time")
        await db.update_one(AiInferenceRequest, {"_id": req.id, "status": "LEASED"}, {"$set": values})
        if not retry and req.run_id:
            runs.add(req.run_id)
    waiting = await db.find(AiInferenceRequest, {"status": "PENDING", "expires_at": {"$lte": now}})
    for req in waiting:
        await db.update_one(
            AiInferenceRequest,
            {"_id": req.id, "status": "PENDING"},
            {
                "$set": {
                    "status": "EXPIRED",
                    "payload": None,
                    "completed_at": now,
                    "error_code": "EXPIRED",
                    "error": "The AI service did not answer before the request expired",
                }
            },
        )
        if req.run_id:
            runs.add(req.run_id)
    return runs
