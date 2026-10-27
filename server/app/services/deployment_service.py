import uuid

from fastapi import HTTPException
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.database import Session
from app.core.dependencies import is_staff
from app.core.ids import parse_uuid
from app.core.timeutil import utcnow
from app.documents.api_key import ApiKey
from app.documents.deployment import Deployment, DeploymentEvent
from app.documents.deployment import DeploymentStatus as S
from app.documents.reservation import ResourceReservation
from app.documents.user import Customer, User
from app.documents.worker import CommandType
from app.schemas.deployment import DeploymentCreate
from app.services import audit_service, billing_service, node_pricing_service, placement_service, worker_service
from app.services import deployment_lifecycle as lifecycle
from app.services.catalog_service import (
    DeploymentConfig,
    deployable_artifacts,
    estimate_requirements,
    get_deployable_model,
    is_unreviewed,
    worker_source,
)
from app.services.placement_service import deploy_payload
from app.services.scheduler_service import NoEligibleNode, release_reservation, schedule


async def _get_customer(db: Session, user_id: uuid.UUID) -> Customer | None:
    return await db.find_one(Customer, {"user_id": user_id})


async def _existing_by_idempotency_key(db: Session, customer_id, key: str | None) -> Deployment | None:
    if not key:
        return None
    return await db.find_one(Deployment, {"customer_id": customer_id, "idempotency_key": key})


async def create_deployment(db: Session, deployment_data: DeploymentCreate, user_id: uuid.UUID):
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
    model = await get_deployable_model(db, deployment_data.model_id, customer.id)
    artifacts = await deployable_artifacts(db, model, deployment_data.runtime)

    deployment = Deployment(
        id=uuid.uuid4(),
        customer_id=customer.id,
        model_id=model.id,
        config=config.model_dump(),
        status=S.REQUESTED.value,
        idempotency_key=deployment_data.idempotency_key,
        max_hourly_price=deployment_data.max_hourly_price,
        max_token_price=deployment_data.max_token_price,
    )
    db.add(deployment)
    try:
        await db.flush()
    except DuplicateKeyError:
        await db.rollback()
        existing = await _existing_by_idempotency_key(db, customer.id, deployment_data.idempotency_key)
        if existing:
            return existing
        raise
    db.add(DeploymentEvent(deployment_id=deployment.id, to_status=S.REQUESTED.value, actor="customer"))

    # Try each compatible runtime in preference order (or only the one the customer asked for).
    node = artifact = req = rates = None
    failures: dict[str, dict] = {}
    for candidate in artifacts:
        candidate_req = estimate_requirements(candidate, config, community=is_unreviewed(model))
        limits = await node_pricing_service.limits_for(
            db,
            deployment_data.max_hourly_price,
            deployment_data.max_token_price,
            candidate_req.cpu_cores,
            candidate_req.ram_mb,
            candidate_req.vram_mb,
        )
        try:
            node, rates = await schedule(db, deployment.id, candidate_req, limits=limits)
        except NoEligibleNode as exc:
            failures[candidate.runtime] = {
                "message": exc.evaluation.explain(),
                "reasons": dict(exc.evaluation.reasons),
                "requirements": candidate_req.__dict__,
            }
            continue
        artifact, req = candidate, candidate_req
        break
    if node is None or artifact is None or req is None:
        await db.rollback()
        merged: dict[str, int] = {}
        for f in failures.values():
            for reason, count in f["reasons"].items():
                merged[reason] = merged.get(reason, 0) + count
        only = next(iter(failures.values())) if len(failures) == 1 else None
        raise HTTPException(
            status_code=503,
            detail={
                "code": "no_eligible_node",
                "message": only["message"]
                if only
                else "; ".join(f"{rt}: {v['message']}" for rt, v in failures.items()),
                "reasons": merged,
                "by_runtime": failures,
                "requirements": only["requirements"] if only else None,
            },
        ) from None

    try:
        await billing_service.require_prepaid(db, user_id, rates, req.cpu_cores, req.ram_mb, req.vram_mb)
    except HTTPException:
        await db.rollback()  # releases the reservation made above
        raise

    deployment.runtime = artifact.runtime
    deployment.model_tag = artifact.reference
    deployment.artifact_id = artifact.id
    deployment.node_id = node.id
    deployment.schedule_attempts = 1
    await lifecycle.transition(
        db, deployment, S.SCHEDULED, actor="system", message="Capacity reserved on a provider node", node_id=node.id
    )
    await worker_service.enqueue_command(
        db, node.id, deployment.id, CommandType.DEPLOY, deploy_payload(deployment, req, worker_source(artifact))
    )
    audit_service.record(
        db,
        actor_id=user_id,
        action="deployment.created",
        resource_type="deployment",
        resource_id=deployment.id,
        details={"model_tag": deployment.model_tag, "runtime": deployment.runtime, "node_id": str(node.id)},
    )
    await db.commit()
    await db.refresh(deployment)
    return deployment


async def list_deployments(db: Session, user_id: uuid.UUID):
    customer = await _get_customer(db, user_id)
    if not customer:
        return []
    return await db.find(Deployment, {"customer_id": customer.id, "deleted_at": None}, sort=[("created_at", -1)])


async def get_deployment_for_user(db: Session, deployment_id: str, user: User) -> Deployment:
    """Fetch a deployment the caller is allowed to see. Non-owners receive 404 so IDs cannot be probed."""
    deployment = await db.get(Deployment, parse_uuid(deployment_id, "Deployment"))
    if deployment and not is_staff(user):
        customer = await _get_customer(db, user.id)
        if not customer or deployment.customer_id != customer.id or deployment.deleted_at is not None:
            deployment = None
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment


async def _stop(db: Session, deployment: Deployment, actor: str, message: str) -> None:
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


async def stop_deployment(db: Session, deployment_id: str, user: User):
    deployment = await get_deployment_for_user(db, deployment_id, user)
    if S(deployment.status) in lifecycle.TERMINAL:
        raise HTTPException(status_code=409, detail=f"Deployment is already {deployment.status}")
    await _stop(db, deployment, actor="customer", message="Stop requested")
    audit_service.record(
        db, actor_id=user.id, action="deployment.stopped", resource_type="deployment", resource_id=deployment.id
    )
    await db.commit()
    return {"status": deployment.status}


async def restart_deployment(db: Session, deployment_id: str, user: User):
    deployment = await get_deployment_for_user(db, deployment_id, user)
    await placement_service.restart(db, deployment)
    audit_service.record(
        db, actor_id=user.id, action="deployment.restarted", resource_type="deployment", resource_id=deployment.id
    )
    await db.commit()
    return {"status": deployment.status}


async def delete_deployment(db: Session, deployment_id: str, user: User):
    """Stop the workload if needed, revoke deployment-scoped API keys, and hide the deployment. Usage and
    lifecycle records are retained for billing and audit."""
    deployment = await get_deployment_for_user(db, deployment_id, user)
    now = utcnow()
    if S(deployment.status) not in lifecycle.TERMINAL:
        await _stop(db, deployment, actor="customer", message="Deletion requested")
    await db.update_many(ApiKey, {"deployment_id": deployment.id, "revoked_at": None}, {"$set": {"revoked_at": now}})
    deployment.deleted_at = now
    audit_service.record(
        db, actor_id=user.id, action="deployment.deleted", resource_type="deployment", resource_id=deployment.id
    )
    await db.commit()
    return {"status": deployment.status, "deleted": True}


async def list_events(db: Session, deployment_id: str, user: User):
    deployment = await get_deployment_for_user(db, deployment_id, user)
    return await db.find(DeploymentEvent, {"deployment_id": deployment.id}, sort=[("created_at", 1), ("_id", 1)])


async def quote(db: Session, body: DeploymentCreate, user_id: uuid.UUID) -> dict:
    """What a deployment would cost before creating it: per runtime, the machine placement would pick now and the
    price limits applied. Reserves nothing."""
    from app.services.scheduler_service import evaluate_nodes

    customer = await _get_customer(db, user_id)
    if not customer:
        raise HTTPException(status_code=403, detail="Customer account required")
    try:
        config = DeploymentConfig(**(body.config or {}))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid config") from exc
    model = await get_deployable_model(db, body.model_id, customer.id)
    out = []
    for artifact in await deployable_artifacts(db, model, body.runtime):
        req = estimate_requirements(artifact, config, community=is_unreviewed(model))
        limits = await node_pricing_service.limits_for(
            db, body.max_hourly_price, body.max_token_price, req.cpu_cores, req.ram_mb, req.vram_mb
        )
        ev = await evaluate_nodes(db, req, limits=limits)
        best = ev.rates[ev.eligible[0].id] if ev.eligible else None
        out.append(
            {
                "runtime": artifact.runtime,
                "requirements": req.__dict__,
                "eligible_nodes": len(ev.eligible),
                "over_price_limit": ev.reasons.get("over_price_limit", 0),
                "cheapest": node_pricing_service.rates_out(best),
                "hourly": best.hourly(req.cpu_cores, req.ram_mb, req.vram_mb) if best else None,
                "max_hourly_price": limits.hourly,
                "max_token_price": limits.tokens,
            }
        )
    return {
        "currency": settings.BILLING_CURRENCY,
        "min_prepaid_hours": settings.BILLING_MIN_PREPAID_HOURS,
        "by_runtime": out,
    }


async def pricing_for(db: Session, deployment_id: str, user: User) -> dict:
    """The rates a deployment is billed at now on its machine, and the most it can be billed there."""
    dep = await get_deployment_for_user(db, deployment_id, user)
    reservation = await db.find_one(ResourceReservation, {"deployment_id": dep.id, "status": "ACTIVE"})
    rates = rule = None
    if reservation is not None:
        placed_at = await billing_service.placement_rates(db, reservation)
        rates, rule = await node_pricing_service.billed_rates(db, reservation.node_id, placed_at, utcnow())
    else:
        placed_at = None
        rule = await node_pricing_service.network_rule(db)
    return {
        "deployment_id": dep.id,
        "currency": settings.BILLING_CURRENCY,
        "rates": node_pricing_service.rates_out(rates),
        "hourly": rates.hourly(reservation.cpu_cores, reservation.ram_mb, reservation.vram_mb)
        if rates is not None and reservation is not None
        else None,
        "placed_at": placed_at,
        "commission_rate": node_pricing_service.commission_rate(rule),
    }
