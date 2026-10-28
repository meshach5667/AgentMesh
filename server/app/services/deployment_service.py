import uuid
from decimal import Decimal

from bson import Decimal128
from fastapi import HTTPException
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from app.core.database import Session
from app.core.dependencies import is_staff
from app.core.ids import parse_uuid
from app.core.timeutil import utcnow
from app.documents.api_key import ApiKey
from app.documents.deployment import Deployment, DeploymentAttempt, DeploymentEvent
from app.documents.deployment import DeploymentStatus as S
from app.documents.node import Node
from app.documents.reservation import ResourceReservation
from app.documents.user import Customer, Provider, User
from app.documents.worker import CommandType
from app.schemas.deployment import DeploymentCreate, DeploymentUpdate
from app.services import (
    audit_service,
    credit_service,
    node_pricing_service,
    placement_service,
    provider_service,
    worker_service,
)
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
    if deployment_data.provider_id is not None:
        await provider_service.get_provider(db, str(deployment_data.provider_id))

    deployment = Deployment(
        id=uuid.uuid4(),
        customer_id=customer.id,
        model_id=model.id,
        config=config.model_dump(),
        status=S.REQUESTED.value,
        idempotency_key=deployment_data.idempotency_key,
        currency=deployment_data.currency,
        max_hourly_price=deployment_data.max_hourly_price,
        max_token_price=deployment_data.max_token_price,
        provider_id=deployment_data.provider_id,
        failover_policy=deployment_data.failover_policy,
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
        limits = node_pricing_service.limits_for(
            deployment_data.currency, deployment_data.max_hourly_price, deployment_data.max_token_price
        )
        providers = {deployment_data.provider_id} if deployment_data.provider_id else None
        try:
            node, rates = await schedule(
                db, deployment.id, candidate_req, limits=limits, providers=providers, customer_id=customer.id
            )
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

    deployment.runtime = artifact.runtime
    deployment.model_tag = artifact.reference
    deployment.artifact_id = artifact.id
    deployment.node_id = node.id
    deployment.schedule_attempts = 1
    await placement_service.start_attempt(db, deployment, node, rates)
    await lifecycle.transition(
        db,
        deployment,
        S.SCHEDULED,
        actor="system",
        message="Capacity reserved on a provider node",
        kind="assigned",
        attempt=1,
        node_id=node.id,
        attempt_id=deployment.attempt_id,
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
    if status in lifecycle.WAITING:
        # Holds no node: nothing to clean up anywhere.
        final = S.STOPPED if deployment.was_ready else S.CANCELLED
        await lifecycle.transition(db, deployment, final, actor=actor, message=message, next_placement_at=None)
        deployment.cleanup_status = "done"
        return
    await placement_service.abort_migration(db, deployment, actor=actor, reason="the deployment was stopped")
    await placement_service.end_attempt(db, deployment, "stopped")
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


async def update_deployment(db: Session, deployment_id: str, body: DeploymentUpdate, user: User) -> Deployment:
    """Change price limits, currency or failover policy. They apply to the next placement (a move after a failure,
    or a retry); a deployment already serving stays where it is."""
    dep = await get_deployment_for_user(db, deployment_id, user)
    if S(dep.status) in lifecycle.TERMINAL:
        raise HTTPException(status_code=409, detail=f"Deployment is already {dep.status}")
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(dep, key, value)
    if changes:
        stored = {k: Decimal128(str(v)) if isinstance(v, Decimal) else v for k, v in changes.items()}
        await db.update_one(Deployment, {"_id": dep.id}, {"$set": stored})
        audit_service.record(
            db,
            actor_id=user.id,
            action="deployment.updated",
            resource_type="deployment",
            resource_id=dep.id,
            details={k: str(v) for k, v in changes.items()},
        )
    await db.commit()
    await db.refresh(dep)
    return dep


async def retry_deployment(db: Session, deployment_id: str, user: User) -> Deployment:
    """Try to place a PENDING or NEEDS_ATTENTION deployment now (for example after raising a price limit)."""
    dep = await get_deployment_for_user(db, deployment_id, user)
    if S(dep.status) not in lifecycle.WAITING:
        raise HTTPException(status_code=409, detail="Only a deployment waiting for a node can be retried")
    await placement_service.retry_placement(db, dep, actor="customer")
    await db.commit()
    await db.refresh(dep)
    return dep


async def list_attempts(db: Session, deployment_id: str, user: User) -> list[dict]:
    """Every placement of the deployment, oldest first, with who ran it and how it ended."""
    dep = await get_deployment_for_user(db, deployment_id, user)
    rows = await db.find(DeploymentAttempt, {"deployment_id": dep.id}, sort=[("number", 1)])
    providers = {
        p.id: p for p in await db.find(Provider, {"_id": {"$in": [r.provider_id for r in rows if r.provider_id]}})
    }
    out = []
    for r in rows:
        prov = providers.get(r.provider_id) if r.provider_id else None
        out.append(
            r.model_dump(
                include={
                    "id",
                    "number",
                    "active",
                    "state",
                    "outcome",
                    "error_code",
                    "error_message",
                    "assigned_at",
                    "ready_at",
                    "ended_at",
                    "rates",
                }
            )
            | {"provider": provider_service.display_name(prov) if prov else None}
        )
    return out


async def quote(db: Session, body: DeploymentCreate, user_id: uuid.UUID) -> dict:
    """What a deployment would cost before creating it: per runtime, the machine placement would pick now within
    the price limits, and who runs it. Reserves nothing."""
    from app.services.scheduler_service import REASON_CURRENCY, REASON_PRICE, evaluate_nodes

    customer = await _get_customer(db, user_id)
    if not customer:
        raise HTTPException(status_code=403, detail="Customer account required")
    try:
        config = DeploymentConfig(**(body.config or {}))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid config") from exc
    model = await get_deployable_model(db, body.model_id, customer.id)
    limits = node_pricing_service.limits_for(body.currency, body.max_hourly_price, body.max_token_price)
    providers = {body.provider_id} if body.provider_id else None
    out = []
    for artifact in await deployable_artifacts(db, model, body.runtime):
        req = estimate_requirements(artifact, config, community=is_unreviewed(model))
        ev = await evaluate_nodes(db, req, limits=limits, providers=providers)
        best_node = ev.eligible[0] if ev.eligible else None
        best = ev.rates[best_node.id] if best_node else None
        provider = await db.get(Provider, best_node.owner_id) if best_node else None
        credit = None
        if best_node is not None and best is not None and not best.is_free():
            have = await credit_service.balance(db, customer.id, best_node.owner_id, best.currency)
            needed = credit_service.credit_needed(best.hourly(req.cpu_cores, req.ram_mb, req.vram_mb))
            credit = {
                "currency": best.currency,
                "balance": have,
                "needed": needed,
                "enough": credit_service.covers(have, best.hourly(req.cpu_cores, req.ram_mb, req.vram_mb)),
            }
        out.append(
            {
                "runtime": artifact.runtime,
                "requirements": req.__dict__,
                "eligible_nodes": len(ev.eligible),
                "over_price_limit": ev.reasons.get(REASON_PRICE, 0),
                "other_currency": ev.reasons.get(REASON_CURRENCY, 0),
                "cheapest": node_pricing_service.rates_out(best),
                "hourly": (best.hourly(req.cpu_cores, req.ram_mb, req.vram_mb) if best else 0) if best_node else None,
                "provider": provider_service.card(provider) if provider else None,
                "credit": credit,
            }
        )
    return {"currency": limits.currency, "by_runtime": out}


async def pricing_for(db: Session, deployment_id: str, user: User) -> dict:
    """What the deployment is estimated at now on its machine, the most it can be estimated at there, and who runs
    that machine and how to pay them."""
    dep = await get_deployment_for_user(db, deployment_id, user)
    reservation = await db.find_one(ResourceReservation, {"deployment_id": dep.id, "status": "ACTIVE"})
    rates = provider = None
    placed_at = None
    if reservation is not None:
        placed_at = reservation.rates
        rates = await node_pricing_service.estimated_rates(db, reservation.node_id, placed_at, utcnow())
        node = await db.get(Node, reservation.node_id)
        provider = await db.get(Provider, node.owner_id) if node else None
    return {
        "deployment_id": dep.id,
        "rates": node_pricing_service.rates_out(rates),
        "hourly": rates.hourly(reservation.cpu_cores, reservation.ram_mb, reservation.vram_mb)
        if rates is not None and reservation is not None
        else (0 if reservation is not None else None),
        "placed_at": placed_at,
        "provider": provider_service.card(provider) if provider else None,
        "payment_reference": str(dep.customer_id)[:8].upper(),
    }
