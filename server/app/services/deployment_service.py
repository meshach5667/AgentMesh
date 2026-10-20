import uuid
from datetime import datetime

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.dependencies import is_staff
from app.core.ids import parse_uuid
from app.models.api_key import ApiKey
from app.models.deployment import Deployment, DeploymentEvent
from app.models.deployment import DeploymentStatus as S
from app.models.user import Customer, User
from app.models.worker import CommandType
from app.schemas.deployment import DeploymentCreate
from app.services import deployment_lifecycle as lifecycle
from app.services import worker_service
from app.services.catalog_service import DeploymentConfig, estimate_requirements, get_deployable_model
from app.services.scheduler_service import NoEligibleNode, release_reservation, schedule

# Kept for callers that predate the lifecycle module.
TERMINAL_STATUSES = lifecycle.TERMINAL


async def _get_customer(db: AsyncSession, user_id: uuid.UUID) -> Customer | None:
    result = await db.execute(select(Customer).filter(Customer.user_id == user_id))
    return result.scalars().first()


async def _existing_by_idempotency_key(db: AsyncSession, customer_id, key: str | None) -> Deployment | None:
    if not key:
        return None
    result = await db.execute(
        select(Deployment).where(Deployment.customer_id == customer_id, Deployment.idempotency_key == key)
    )
    return result.scalars().first()


def deploy_payload(deployment: Deployment, req) -> dict:
    """The only information sent to a worker: validated identifiers and limits. No customer credentials and
    no free-form runtime arguments."""
    return {
        "deployment_id": str(deployment.id),
        "runtime": deployment.runtime,
        "model_tag": deployment.model_tag,
        "num_ctx": deployment.config["num_ctx"],
        "resources": {
            "cpu_cores": req.cpu_cores,
            "ram_mb": req.ram_mb,
            "disk_mb": req.disk_mb,
            "vram_mb": req.vram_mb,
            "gpu": req.gpu_required,
        },
        "timeouts": {
            "stall_seconds": settings.PROVISION_STALL_TIMEOUT_SECONDS,
            "max_seconds": settings.PROVISION_MAX_SECONDS,
        },
    }


async def create_deployment(db: AsyncSession, deployment_data: DeploymentCreate, user_id: uuid.UUID):
    customer = await _get_customer(db, user_id)
    if not customer:
        raise HTTPException(status_code=403, detail="Customer account required")

    existing = await _existing_by_idempotency_key(db, customer.id, deployment_data.idempotency_key)
    if existing:
        return existing

    try:
        config = DeploymentConfig(**(deployment_data.config or {}))
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body", "config", *e["loc"]], "msg": e["msg"], "type": e["type"]} for e in exc.errors()],
        ) from None
    model = await get_deployable_model(db, deployment_data.model_id)
    req = estimate_requirements(model, config)

    deployment = Deployment(
        id=uuid.uuid4(),
        customer_id=customer.id,
        model_id=model.id,
        runtime=model.runtime,
        model_tag=model.model_tag,
        config=config.model_dump(),
        status=S.REQUESTED.value,
        idempotency_key=deployment_data.idempotency_key,
    )
    db.add(deployment)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        existing = await _existing_by_idempotency_key(db, customer.id, deployment_data.idempotency_key)
        if existing:
            return existing
        raise
    db.add(DeploymentEvent(deployment_id=deployment.id, to_status=S.REQUESTED.value, actor="customer"))

    try:
        node = await schedule(db, deployment.id, req)
    except NoEligibleNode as exc:
        await db.rollback()
        raise HTTPException(
            status_code=503,
            detail={
                "code": "no_eligible_node",
                "message": exc.evaluation.explain(),
                "reasons": dict(exc.evaluation.reasons),
                "requirements": req.__dict__,
            },
        ) from None

    deployment.node_id = node.id
    await lifecycle.transition(
        db, deployment, S.SCHEDULED, actor="system", message="Capacity reserved on a provider node", node_id=node.id
    )
    await worker_service.enqueue_command(
        db, node.id, deployment.id, CommandType.DEPLOY, deploy_payload(deployment, req)
    )
    await db.commit()
    await db.refresh(deployment)
    return deployment


async def list_deployments(db: AsyncSession, user_id: uuid.UUID):
    customer = await _get_customer(db, user_id)
    if not customer:
        return []
    result = await db.execute(
        select(Deployment)
        .filter(Deployment.customer_id == customer.id, Deployment.deleted_at.is_(None))
        .order_by(Deployment.created_at.desc())
    )
    return result.scalars().all()


async def get_deployment_for_user(db: AsyncSession, deployment_id: str, user: User) -> Deployment:
    """Fetch a deployment the caller is allowed to see. Non-owners receive 404 so IDs cannot be probed."""
    result = await db.execute(select(Deployment).filter(Deployment.id == parse_uuid(deployment_id, "Deployment")))
    deployment = result.scalars().first()
    if deployment and not is_staff(user):
        customer = await _get_customer(db, user.id)
        if not customer or deployment.customer_id != customer.id or deployment.deleted_at is not None:
            deployment = None
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment


async def _stop(db: AsyncSession, deployment: Deployment, actor: str, message: str) -> None:
    """Begin stopping a non-terminal deployment. Does not commit."""
    status = S(deployment.status)
    if status == S.STOPPING:
        return
    if status == S.REQUESTED:
        await lifecycle.transition(db, deployment, S.CANCELLED, actor=actor, message=message)
        return
    await lifecycle.transition(db, deployment, S.STOPPING, actor=actor, message=message)
    if status == S.SCHEDULED and await worker_service.cancel_undelivered(db, deployment.id, CommandType.DEPLOY):
        # The worker never received the deploy command, so there is nothing to clean up on the node.
        await lifecycle.transition(db, deployment, S.CANCELLED, actor="system", message="Cancelled before delivery")
        deployment.cleanup_status = "done"
        await release_reservation(db, deployment.id)
        return
    deployment.cleanup_status = "pending"
    await worker_service.enqueue_command(
        db, deployment.node_id, deployment.id, CommandType.STOP, {"deployment_id": str(deployment.id)}
    )


async def stop_deployment(db: AsyncSession, deployment_id: str, user: User):
    deployment = await get_deployment_for_user(db, deployment_id, user)
    if S(deployment.status) in lifecycle.TERMINAL:
        raise HTTPException(status_code=409, detail=f"Deployment is already {deployment.status}")
    await _stop(db, deployment, actor="customer", message="Stop requested")
    await db.commit()
    return {"status": deployment.status}


async def delete_deployment(db: AsyncSession, deployment_id: str, user: User):
    """Stop the workload if needed, revoke deployment-scoped API keys, and hide the deployment. Usage and
    lifecycle records are retained for billing and audit."""
    deployment = await get_deployment_for_user(db, deployment_id, user)
    now = datetime.utcnow()
    if S(deployment.status) not in lifecycle.TERMINAL:
        await _stop(db, deployment, actor="customer", message="Deletion requested")
    await db.execute(
        update(ApiKey)
        .where(ApiKey.deployment_id == deployment.id, ApiKey.revoked_at.is_(None))
        .values(revoked_at=now)
        .execution_options(synchronize_session=False)
    )
    deployment.deleted_at = now
    await db.commit()
    return {"status": deployment.status, "deleted": True}


async def list_events(db: AsyncSession, deployment_id: str, user: User):
    deployment = await get_deployment_for_user(db, deployment_id, user)
    result = await db.execute(
        select(DeploymentEvent)
        .where(DeploymentEvent.deployment_id == deployment.id)
        .order_by(DeploymentEvent.created_at, DeploymentEvent.id)
    )
    return result.scalars().all()
