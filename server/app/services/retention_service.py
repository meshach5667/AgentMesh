"""Scheduled deletion of data past its retention period, per data class (docs/security/DATA_HANDLING.md).

Prompts sent through the inference gateway are never stored. What is stored and how long it is kept:

* AI deployment agent: a run's request text, plan, events and model calls. Model-call prompts are erased as soon as
  they are answered; outputs after ``AI_INFERENCE_RESULT_RETENTION_HOURS``; finished runs with everything attached
  after ``AI_RUN_RETENTION_DAYS``.
* Per-request usage records (metadata only): ``USAGE_RECORD_RETENTION_DAYS``. Rated charges and the ledger are
  financial records and are never deleted here.
* Deployment events: ``DEPLOYMENT_EVENT_RETENTION_DAYS``. Audit log: ``AUDIT_LOG_RETENTION_DAYS``.
* Sessions, challenges, refresh tokens and sponsored-view tokens expire through TTL indexes.

Backups keep deleted data until they rotate out (see the operator docs).
"""

import logging
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import Session, session_scope
from app.core.timeutil import utcnow
from app.documents.ai import AiInferenceRequest, AiRun, AiRunEvent
from app.documents.audit import AuditLog
from app.documents.deployment import DeploymentEvent
from app.documents.usage import UsageRecord

logger = logging.getLogger(__name__)
FINISHED_RUN = ["COMPLETED", "FAILED", "CANCELLED"]
DONE_REQUEST = ["COMPLETED", "FAILED", "EXPIRED", "CANCELLED"]


async def delete_runs(db: Session, run_ids: list) -> dict[str, int]:
    """Delete AI runs with their events and model calls. The caller commits."""
    return {
        "inference_requests": await db.delete_many(AiInferenceRequest, {"run_id": {"$in": run_ids}}),
        "events": await db.delete_many(AiRunEvent, {"run_id": {"$in": run_ids}}),
        "runs": await db.delete_many(AiRun, {"_id": {"$in": run_ids}}),
    }


async def purge(db: Session, now: datetime | None = None) -> dict[str, int]:
    now = now or utcnow()
    days = lambda n: now - timedelta(days=n)  # noqa: E731
    counts: dict[str, int] = {}
    counts["inference_results_erased"] = await db.update_many(
        AiInferenceRequest,
        {
            "status": {"$in": DONE_REQUEST},
            "created_at": {"$lt": now - timedelta(hours=settings.AI_INFERENCE_RESULT_RETENTION_HOURS)},
            "$or": [{"result": {"$ne": None}}, {"payload": {"$ne": None}}],
        },
        {"$set": {"result": None, "payload": None}},
    )
    old_runs = await db.distinct(
        AiRun, "_id", {"status": {"$in": FINISHED_RUN}, "created_at": {"$lt": days(settings.AI_RUN_RETENTION_DAYS)}}
    )
    for key, value in (await delete_runs(db, old_runs)).items():
        counts[f"ai_{key}"] = value
    counts["orphan_inference_requests"] = await db.delete_many(
        AiInferenceRequest, {"created_at": {"$lt": days(settings.AI_RUN_RETENTION_DAYS)}}
    )
    counts["usage_records"] = await db.delete_many(
        UsageRecord, {"created_at": {"$lt": days(settings.USAGE_RECORD_RETENTION_DAYS)}}
    )
    counts["deployment_events"] = await db.delete_many(
        DeploymentEvent, {"created_at": {"$lt": days(settings.DEPLOYMENT_EVENT_RETENTION_DAYS)}}
    )
    counts["audit_logs"] = await db.delete_many(
        AuditLog, {"created_at": {"$lt": days(settings.AUDIT_LOG_RETENTION_DAYS)}}
    )
    await db.commit()
    return counts


async def run_retention() -> dict[str, int]:
    async with session_scope() as db:
        counts = await purge(db)
    if any(counts.values()):
        logger.info("Retention purge: %s", ", ".join(f"{k}={v}" for k, v in counts.items() if v))
    return counts
