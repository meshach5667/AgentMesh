"""AI deployment agent API.

Customers:
    POST /ai/deployments               describe a deployment and authorize limits (starts a run)
    GET  /ai/deployments               list runs
    GET  /ai/deployments/{id}          progress, plan, estimated and actual cost, verified endpoint
    POST /ai/deployments/{id}/cancel   stop the run and any deployment it created
    GET  /ai/deployments/{id}/events   run history
    DELETE /ai/deployments/{id}        delete a finished run and everything stored for it
    GET  /ai/health                    whether the AI service is available

The agent's model calls are answered by the Gemini API (app.services.ai.gemini).
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.core.config import settings
from app.core.database import Session, get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.ratelimit import limiters
from app.documents.ai import AiRun, AiRunEvent
from app.documents.user import Customer, User, UserRole
from app.schemas.ai import (
    AiDeploymentCreate,
    AiHealthOut,
    AiRunEventOut,
    AiRunOut,
)
from app.services.ai import inference_queue, workflow

router = APIRouter()


async def _advance_quietly(run_id: uuid.UUID) -> None:
    try:
        await workflow.advance(run_id)
    except Exception:  # noqa: BLE001
        pass  # logged by advance; the background monitor retries


# --- Customers -----------------------------------------------------------------------------------------


@router.post("/deployments", response_model=AiRunOut, status_code=202)
async def create_ai_deployment(
    body: AiDeploymentCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.customer)),
):
    allowed, retry_after = await limiters.requests.allow(f"ai-run:{user.id}", settings.AI_RATE_LIMIT_PER_MINUTE)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many AI deployment requests",
            headers={"Retry-After": str(max(1, int(retry_after)))},
        )
    run = await workflow.create_run(db, user, body.request, body.limits, body.idempotency_key)
    background.add_task(_advance_quietly, run.id)
    return await workflow.view(db, run)


@router.get("/deployments", response_model=list[AiRunOut])
async def list_ai_deployments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    customer = await db.find_one(Customer, {"user_id": user.id})
    if customer is None:
        return []
    runs = await db.find(AiRun, {"customer_id": customer.id}, sort=[("created_at", -1)], limit=100)
    return [await workflow.view(db, r) for r in runs]


@router.get("/deployments/{run_id}", response_model=AiRunOut)
async def get_ai_deployment(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return await workflow.view(db, await workflow.get_run_for_user(db, run_id, user))


@router.post("/deployments/{run_id}/cancel", response_model=AiRunOut)
async def cancel_ai_deployment(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = await workflow.get_run_for_user(db, run_id, user)
    await workflow.request_cancel(db, run, user)
    await workflow.advance(run.id)
    return await workflow.view(db, await workflow.get_run_for_user(db, run_id, user))


@router.delete("/deployments/{run_id}")
async def delete_ai_deployment(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Delete a finished AI deployment run: its request text, plan, events and model calls. Deployments it created
    are separate and are stopped or deleted on their own. Returns what was deleted."""
    from app.services import audit_service, retention_service

    run = await workflow.get_run_for_user(db, run_id, user)
    if run.status not in retention_service.FINISHED_RUN:
        raise HTTPException(status_code=409, detail="Cancel the run and wait for it to finish before deleting it")
    deleted = await retention_service.delete_runs(db, [run.id])
    audit_service.record(
        db, actor_id=user.id, action="ai.run_deleted", resource_type="ai_run", resource_id=run.id, details=deleted
    )
    await db.commit()
    return {"deleted": deleted, "note": "Removed from the live database now; backups expire on their own schedule."}


@router.get("/deployments/{run_id}/events", response_model=list[AiRunEventOut])
async def ai_deployment_events(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = await workflow.get_run_for_user(db, run_id, user)
    rows = await db.find(AiRunEvent, {"run_id": run.id}, sort=[("created_at", -1), ("_id", -1)], limit=500)
    return rows[::-1]


@router.get("/health", response_model=AiHealthOut)
async def ai_health(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    h = await inference_queue.health(db)
    return AiHealthOut(
        status=h.status, available=h.available, model=h.model, queue_depth=h.queue_depth, message=h.message
    )
