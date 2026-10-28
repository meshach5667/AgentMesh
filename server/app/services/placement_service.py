"""Execution attempts and recovery: what happens when a deployment's node fails.

Every placement of a deployment on a node is a DeploymentAttempt. When the node fails (stops heartbeating, stays
unhealthy, rejects or never picks up the work, or the workload exits), the attempt ends and AgentMesh decides:

* Failures caused by the model (bad tag, failed test generation, download error after the worker's own retries)
  are not retried elsewhere, because another node would fail the same way: FAILED.
* After MAX_SCHEDULE_ATTEMPTS placements it gives up: FAILED (retry limit).
* With the customer's "manual" failover policy it does not move the deployment by itself: NEEDS_ATTENTION.
* Otherwise it reserves the cheapest eligible replacement (same requirements, the customer's provider and price
  constraints, never a node that already failed it) and dispatches the deployment there as a new attempt. When the
  only nodes that fit cost more than the customer approved, it waits for approval (NEEDS_ATTENTION); when none fit
  at all, it waits as PENDING and retries with exponential backoff and jitter until PLACEMENT_PENDING_MAX_SECONDS.

Serving a model is restartable (the runtime loads it again from its pinned source), so a move is a restart on the
new node, never a live migration of in-memory state; in-flight requests on the failed node are lost and are not
replayed (customers retry them). A deployment keeps its id, endpoint and API keys when it moves. Assignment is
concurrency-safe: reservations and attempts each allow one active row per deployment (unique partial indexes), state
changes are compare-and-set, and workers' reports for an attempt that is no longer current are refused.
"""

import logging
import random
import uuid
from datetime import timedelta
from typing import Any

from fastapi import HTTPException

from app.core.config import settings
from app.core.database import Session
from app.core.timeutil import utcnow
from app.documents.deployment import Deployment, DeploymentAttempt
from app.documents.deployment import DeploymentStatus as S
from app.documents.model import Model, ModelArtifact
from app.documents.node import Node, NodeStatus
from app.documents.reservation import ResourceReservation
from app.documents.worker import CommandType
from app.services import audit_service, node_pricing_service
from app.services import deployment_lifecycle as lifecycle
from app.services.catalog_service import (
    DeploymentConfig,
    ResourceRequest,
    estimate_requirements,
    is_unreviewed,
    worker_source,
)
from app.services.commands import cancel_undelivered, enqueue_command
from app.services.node_pricing_service import Rates
from app.services.scheduler_service import (
    REASON_CURRENCY,
    REASON_NO_CREDIT,
    REASON_PRICE,
    NoEligibleNode,
    node_is_fresh,
    release_reservation,
    release_standby,
    schedule,
)

logger = logging.getLogger(__name__)

# Failure codes that are the node's fault and worth retrying on a different node.
RESCHEDULABLE_CODES = frozenset(
    {
        "NODE_UNRESPONSIVE",  # never picked up the deploy command
        "NODE_OFFLINE",  # stopped heartbeating while provisioning
        "NODE_REVOKED",
        "NODE_QUARANTINED",
        "PROVISION_STALLED",
        "UNHEALTHY_TIMEOUT",
        "INSUFFICIENT_MEMORY",
        "INSUFFICIENT_DISK",
        "RUNTIME_START_FAILED",
        "RUNTIME_IMAGE_UNAVAILABLE",
        "MODEL_PULL_STALLED",
        "WORKLOAD_EXITED",
        "NODE_UNAVAILABLE",  # provider paused/drained the machine locally or its schedule ended
        "RUNTIME_UNAVAILABLE",  # the node no longer offers the runtime (stale capabilities)
        "WORKER_ERROR",  # unexpected worker failure: another node may not hit it (placements are bounded)
    }
)


async def artifact_for(db: Session, dep: Deployment) -> ModelArtifact:
    artifact = await db.get(ModelArtifact, dep.artifact_id) if dep.artifact_id else None
    if artifact is None:  # deployments created before artifacts existed
        artifact = await db.find_one(ModelArtifact, {"model_id": dep.model_id, "runtime": dep.runtime})
    if artifact is None:
        raise ValueError(f"Deployment {dep.id} has no runtime artifact")
    return artifact


async def requirements_for(db: Session, dep: Deployment) -> ResourceRequest:
    model = await db.get(Model, dep.model_id)
    return estimate_requirements(
        await artifact_for(db, dep),
        DeploymentConfig(**(dep.config or {})),
        community=model is not None and is_unreviewed(model),
    )


def deploy_payload(dep: Deployment, req: ResourceRequest, source: dict | None = None) -> dict[str, Any]:
    """The only information sent to a worker: validated identifiers, a pinned model source, and limits. No
    customer credentials and no free-form runtime arguments."""
    return {
        "deployment_id": str(dep.id),
        "attempt_id": str(dep.attempt_id) if dep.attempt_id else None,
        "runtime": dep.runtime,
        "model_tag": dep.model_tag,
        "source": source,
        "num_ctx": (dep.config or {}).get("num_ctx", 2048),
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


FAILOVER_POLICIES = ("any_provider", "same_provider", "manual")


# --- Attempts ----------------------------------------------------------------------------------------------


async def start_attempt(db: Session, dep: Deployment, node: Node, rates: Rates | None) -> DeploymentAttempt:
    """Record a new placement of ``dep`` on ``node`` and make it current. The unique partial index on active
    attempts rejects a second concurrent assignment. Does not commit."""
    newest = await db.find_one(DeploymentAttempt, {"deployment_id": dep.id}, sort=[("number", -1)])
    attempt = DeploymentAttempt(
        deployment_id=dep.id,
        number=(newest.number if newest else 0) + 1,
        node_id=node.id,
        provider_id=node.owner_id,
        rates=(rates or Rates.free()).snapshot(),
    )
    db.add(attempt)
    await db.flush()
    dep.attempt_id = attempt.id
    _set_credit_source(dep, node, rates)
    return attempt


def _set_credit_source(dep: Deployment, node: Node, rates: Rates | None) -> None:
    """Which provider's prepaid credit the deployment draws on at its current placement (none on a free machine)."""
    priced = rates is not None and not rates.is_free()
    dep.priced = priced
    dep.credit_provider_id = node.owner_id if priced else None
    dep.credit_currency = rates.currency if priced and rates is not None else None


async def current_attempt(db: Session, dep: Deployment) -> DeploymentAttempt | None:
    return await db.get(DeploymentAttempt, dep.attempt_id) if dep.attempt_id else None


async def end_attempt(
    db: Session, dep: Deployment, outcome: str, code: str | None = None, message: str | None = None
) -> DeploymentAttempt | None:
    """End the current attempt (once; later calls change nothing). Does not commit."""
    attempt = await current_attempt(db, dep)
    if attempt is None or not attempt.active:
        return attempt
    values = {
        "active": False,
        "state": "ended",
        "outcome": outcome,
        "error_code": code,
        "error_message": (message or "")[:500] or None,
        "ended_at": utcnow(),
    }
    if await db.update_one(DeploymentAttempt, {"_id": attempt.id, "active": True}, {"$set": values}):
        for k, v in values.items():
            setattr(attempt, k, v)
    return attempt


async def mark_attempt_running(db: Session, dep: Deployment) -> None:
    """The current attempt served (READY): the node did its job, so its failure streak resets. Does not commit."""
    attempt = await current_attempt(db, dep)
    if attempt is not None and attempt.active and attempt.state != "running":
        await db.update_one(
            DeploymentAttempt, {"_id": attempt.id}, {"$set": {"state": "running", "ready_at": utcnow()}}
        )
    if dep.node_id:
        await db.update_one(Node, {"_id": dep.node_id}, {"$set": {"consecutive_failures": 0}})


async def note_node_failure(db: Session, node_id: uuid.UUID, code: str) -> None:
    """Count a failure caused by the node. NODE_FAILURE_THRESHOLD in a row keep it out of scheduling for
    NODE_DEGRADED_COOLDOWN_SECONDS. Does not commit."""
    node = await db.get(Node, node_id)
    if node is None:
        return
    count = (node.consecutive_failures or 0) + 1
    fields: dict[str, Any] = {"consecutive_failures": count}
    if count >= settings.NODE_FAILURE_THRESHOLD:
        fields = {
            "consecutive_failures": 0,
            "degraded_until": utcnow() + timedelta(seconds=settings.NODE_DEGRADED_COOLDOWN_SECONDS),
        }
        audit_service.record(
            db,
            actor_id=None,
            action="node.degraded",
            resource_type="node",
            resource_id=node_id,
            details={"reason": f"{count} failed placements in a row", "last_error": code},
        )
    await db.update_one(Node, {"_id": node_id}, {"$set": fields})
    for k, v in fields.items():
        setattr(node, k, v)


# --- Recovery ----------------------------------------------------------------------------------------------


async def _stop_on_old_node(db: Session, dep: Deployment, node_id: uuid.UUID) -> None:
    # If the old node never received the deploy, there is nothing to clean up there.
    if not await cancel_undelivered(db, dep.id, CommandType.DEPLOY):
        await enqueue_command(db, node_id, dep.id, CommandType.STOP, {"deployment_id": str(dep.id)})


def _backoff(retries: int) -> timedelta:
    """Exponential backoff with +/-20% jitter, capped at PLACEMENT_RETRY_MAX_SECONDS."""
    base = min(settings.PLACEMENT_RETRY_MAX_SECONDS, settings.PLACEMENT_RETRY_BASE_SECONDS * 2 ** min(retries, 16))
    return timedelta(seconds=base * random.uniform(0.8, 1.2))  # noqa: S311 - jitter, not security


async def _excluded(dep: Deployment) -> set[uuid.UUID]:
    return {uuid.UUID(str(n)) for n in (dep.excluded_node_ids or [])}


async def _providers(db: Session, dep: Deployment, last: DeploymentAttempt | None) -> set | None:
    """Providers the deployment may run on: the one the customer chose, or with the same_provider policy the
    provider of its last placement."""
    if dep.provider_id is not None:
        return {dep.provider_id}
    if dep.failover_policy == "same_provider" and last is not None and last.provider_id is not None:
        return {last.provider_id}
    return None


async def place(db: Session, dep: Deployment, *, actor: str, note: str, last: DeploymentAttempt | None) -> Node:
    """Reserve the best eligible node for a deployment that has none, start an attempt there and dispatch it.
    Raises NoEligibleNode. Does not commit."""
    req = await requirements_for(db, dep)
    source = worker_source(await artifact_for(db, dep))
    replacing = Rates.from_snapshot(last.rates) if last is not None and last.rates else None
    limits = node_pricing_service.limits_for(
        dep.currency,
        dep.max_hourly_price,
        dep.max_token_price,
        replacing=replacing,
        cpu_cores=req.cpu_cores,
        ram_mb=req.ram_mb,
        vram_mb=req.vram_mb,
    )
    node, rates = await schedule(
        db,
        dep.id,
        req,
        exclude=await _excluded(dep),
        limits=limits,
        providers=await _providers(db, dep, last),
        customer_id=dep.customer_id,
    )
    await start_attempt(db, dep, node, rates)
    fields: dict[str, Any] = {
        "node_id": node.id,
        "attempt_id": dep.attempt_id,
        "priced": dep.priced,
        "credit_provider_id": dep.credit_provider_id,
        "credit_currency": dep.credit_currency,
        "schedule_attempts": dep.schedule_attempts + 1,
        "next_placement_at": None,
        "pending_since": None,
        "placement_retries": 0,
    }
    number = dep.schedule_attempts + 1
    if S(dep.status) == S.SCHEDULED:
        for key, value in fields.items():
            setattr(dep, key, value)
        dep.updated_at = utcnow()
        await db.update_one(Deployment, {"_id": dep.id}, {"$set": fields | {"updated_at": dep.updated_at}})
        await lifecycle.record_event(db, dep, actor=actor, message=note, kind="rerouted", attempt=number)
    elif not await lifecycle.transition(
        db, dep, S.SCHEDULED, actor=actor, message=note, kind="rerouted", attempt=number, **fields
    ):
        raise RuntimeError(f"Deployment {dep.id} changed state concurrently")
    await enqueue_command(db, node.id, dep.id, CommandType.DEPLOY, deploy_payload(dep, req, source))
    return node


def _needs_price_approval(dep: Deployment, exc: NoEligibleNode) -> bool:
    """Only nodes that cost more than the placement being replaced fit, and the customer set no limit of their own:
    moving there needs the customer's approval."""
    reasons = exc.evaluation.reasons
    priced_out = reasons.get(REASON_PRICE, 0) + reasons.get(REASON_CURRENCY, 0)
    return priced_out > 0 and dep.max_hourly_price is None and dep.max_token_price is None


async def _wait(db: Session, dep: Deployment, *, actor: str, exc: NoEligibleNode, number: int) -> None:
    """No node fits now: wait for approval (dearer nodes only), for prepaid credit, or retry later (PENDING).
    Does not commit."""
    now = utcnow()
    if exc.evaluation.reasons.get(REASON_NO_CREDIT, 0) > 0 and not _needs_price_approval(dep, exc):
        await lifecycle.transition(
            db,
            dep,
            S.NEEDS_ATTENTION,
            actor=actor,
            message=(
                "The machines that could run it need prepaid credit with their provider. Buy credit with a provider; "
                "the deployment is placed automatically once the payment is verified."
            ),
            error_code="CREDIT_EXHAUSTED",
            kind="credit_required",
            attempt=number,
            node_id=None,
        )
        return
    if _needs_price_approval(dep, exc):
        message = (
            "Only machines that cost more than the previous placement are available. Approve a higher price "
            "(set max_hourly_price / max_token_price) and retry, or wait and retry later."
        )
        await lifecycle.transition(
            db,
            dep,
            S.NEEDS_ATTENTION,
            actor=actor,
            message=message,
            error_code="PRICE_APPROVAL_REQUIRED",
            kind="approval_required",
            attempt=number,
            node_id=None,
        )
        return
    delay = _backoff(dep.placement_retries)
    message = f"{exc.evaluation.explain()} Retrying in {int(delay.total_seconds())} s."
    fields = {
        "node_id": None,
        "next_placement_at": now + delay,
        "pending_since": dep.pending_since or now,
    }
    if S(dep.status) == S.PENDING:
        await db.update_one(Deployment, {"_id": dep.id}, {"$set": fields})
        for k, v in fields.items():
            setattr(dep, k, v)
        await lifecycle.record_event(db, dep, actor=actor, message=message, kind="retry_scheduled", attempt=number)
    else:
        await lifecycle.transition(
            db,
            dep,
            S.PENDING,
            actor=actor,
            message=message,
            error_code="NO_ELIGIBLE_NODE",
            kind="no_replacement",
            attempt=number,
            **fields,
        )


async def fail_or_reschedule(
    db: Session,
    dep: Deployment,
    *,
    code: str,
    message: str,
    actor: str,
    cleanup_old_node: bool,
) -> bool:
    """Handle a failure of the deployment's current attempt. Returns True if it was moved to another node now;
    otherwise it is FAILED, PENDING (retrying) or NEEDS_ATTENTION. Releases the old reservation either way.
    Does not commit."""
    status = S(dep.status)
    if status in lifecycle.TERMINAL or status in (S.PENDING, S.NEEDS_ATTENTION, S.STOPPING):
        return False
    await abort_migration(db, dep, actor=actor, reason="the deployment's current node failed")
    old_node = dep.node_id
    await release_reservation(db, dep.id)
    node_fault = code in RESCHEDULABLE_CODES
    last = await end_attempt(db, dep, "node_failed" if node_fault else "workload_failed", code, message)
    number = last.number if last else dep.schedule_attempts
    if node_fault and old_node:
        await note_node_failure(db, old_node, code)
    if old_node and cleanup_old_node:
        await _stop_on_old_node(db, dep, old_node)
    await lifecycle.record_event(
        db, dep, actor=actor, message=f"Attempt {number} failed: {message}", kind="attempt_failed", attempt=number
    )

    if status == S.READY:
        # Serving deployments pass through UNHEALTHY so the history shows the outage.
        await lifecycle.transition(db, dep, S.UNHEALTHY, actor=actor, message=message)
        status = S.UNHEALTHY

    if not node_fault or dep.deleted_at is not None:
        await lifecycle.transition(db, dep, S.FAILED, actor=actor, message=message, error_code=code)
        if old_node and cleanup_old_node:
            dep.cleanup_status = "pending"
        return False
    if dep.schedule_attempts >= settings.MAX_SCHEDULE_ATTEMPTS:
        await lifecycle.transition(
            db,
            dep,
            S.FAILED,
            actor=actor,
            message=f"{message}. Gave up after {dep.schedule_attempts} placements (retry limit)",
            error_code=code,
            kind="retry_limit",
            attempt=number,
        )
        return False

    excluded = await _excluded(dep)
    if old_node:
        excluded.add(old_node)
    dep.excluded_node_ids = sorted(str(n) for n in excluded)
    dep.error_code, dep.error_message = code, message
    await db.update_one(
        Deployment,
        {"_id": dep.id},
        {"$set": {"excluded_node_ids": dep.excluded_node_ids, "error_code": code, "error_message": message}},
    )

    if dep.failover_policy == "manual":
        await lifecycle.transition(
            db,
            dep,
            S.NEEDS_ATTENTION,
            actor=actor,
            message=f"{message}. Your failover policy is manual: retry it when you are ready.",
            error_code=code,
            kind="approval_required",
            attempt=number,
            node_id=None,
        )
        return False

    try:
        node = await place(
            db,
            dep,
            actor=actor,
            note=f"{message}. Moved to another node (placement {dep.schedule_attempts + 1})",
            last=last,
        )
    except NoEligibleNode as exc:
        await _wait(db, dep, actor=actor, exc=exc, number=number)
        return False
    audit_service.record(
        db,
        actor_id=None,
        action="deployment.moved",
        resource_type="deployment",
        resource_id=dep.id,
        details={"from_node": str(old_node) if old_node else None, "to_node": str(node.id), "reason": code},
    )
    logger.info("Deployment %s moved from node %s to %s (%s)", dep.id, old_node, node.id, code)
    return True


async def retry_placement(db: Session, dep: Deployment, *, actor: str) -> bool:
    """Try to place a PENDING or NEEDS_ATTENTION deployment now. Returns True if it was placed; otherwise it waits
    (PENDING, with backoff) or fails once PLACEMENT_PENDING_MAX_SECONDS have passed. Does not commit."""
    status = S(dep.status)
    if status not in (S.PENDING, S.NEEDS_ATTENTION):
        return False
    now = utcnow()
    last = await db.find_one(DeploymentAttempt, {"deployment_id": dep.id}, sort=[("number", -1)])
    number = last.number if last else dep.schedule_attempts
    if dep.schedule_attempts >= settings.MAX_SCHEDULE_ATTEMPTS:
        await lifecycle.transition(
            db, dep, S.FAILED, actor=actor, message="Retry limit reached", error_code="RETRY_LIMIT", kind="retry_limit"
        )
        return False
    if (
        status == S.PENDING
        and dep.pending_since is not None
        and now - dep.pending_since > timedelta(seconds=settings.PLACEMENT_PENDING_MAX_SECONDS)
    ):
        await lifecycle.transition(
            db,
            dep,
            S.FAILED,
            actor=actor,
            message=f"No eligible node became available within {settings.PLACEMENT_PENDING_MAX_SECONDS} s",
            error_code="NO_ELIGIBLE_NODE",
            kind="retry_limit",
            attempt=number,
        )
        return False
    try:
        await place(
            db,
            dep,
            actor=actor,
            note=f"Placed on a replacement node (placement {dep.schedule_attempts + 1})",
            last=last,
        )
    except NoEligibleNode as exc:
        if status == S.PENDING:
            dep.placement_retries += 1
            await db.update_one(Deployment, {"_id": dep.id}, {"$set": {"placement_retries": dep.placement_retries}})
        await _wait(db, dep, actor=actor, exc=exc, number=number)
        return False
    return True


# --- Planned moves (make-before-break) ---------------------------------------------------------------------


async def start_migration(db: Session, dep: Deployment, *, actor: str, reason: str) -> Node | None:
    """Start moving a serving deployment to another node without interrupting it: reserve capacity there and start a
    standby attempt while the current node keeps serving. Traffic switches when the standby reports READY
    (complete_migration). Returns the target node, or None when no move was started (not serving, already moving,
    the customer chose manual failover, or no eligible node). Does not commit."""
    if S(dep.status) != S.READY or dep.migrating_attempt_id is not None or dep.failover_policy == "manual":
        return None
    current = await current_attempt(db, dep)
    req = await requirements_for(db, dep)
    source = worker_source(await artifact_for(db, dep))
    replacing = Rates.from_snapshot(current.rates) if current is not None and current.rates else None
    limits = node_pricing_service.limits_for(
        dep.currency,
        dep.max_hourly_price,
        dep.max_token_price,
        replacing=replacing,
        cpu_cores=req.cpu_cores,
        ram_mb=req.ram_mb,
        vram_mb=req.vram_mb,
    )
    exclude = await _excluded(dep)
    if dep.node_id:
        exclude.add(dep.node_id)
    try:
        node, rates = await schedule(
            db,
            dep.id,
            req,
            exclude=exclude,
            limits=limits,
            providers=await _providers(db, dep, current),
            customer_id=dep.customer_id,
            standby=True,
        )
    except NoEligibleNode as exc:
        await lifecycle.record_event(
            db,
            dep,
            actor=actor,
            message=f"Could not start a planned move ({reason}): {exc.evaluation.explain()} It keeps running here.",
            kind="migration_skipped",
        )
        return None
    newest = await db.find_one(DeploymentAttempt, {"deployment_id": dep.id}, sort=[("number", -1)])
    attempt = DeploymentAttempt(
        deployment_id=dep.id,
        number=(newest.number if newest else 0) + 1,
        node_id=node.id,
        provider_id=node.owner_id,
        active=False,
        state="standby",
        rates=(rates or Rates.free()).snapshot(),
    )
    db.add(attempt)
    await db.flush()
    now = utcnow()
    fields = {"migrating_attempt_id": attempt.id, "migrating_node_id": node.id, "migration_started_at": now}
    if not await db.update_one(
        Deployment, {"_id": dep.id, "status": S.READY.value, "migrating_attempt_id": None}, {"$set": fields}
    ):
        raise RuntimeError(f"Deployment {dep.id} changed state concurrently")
    for k, v in fields.items():
        setattr(dep, k, v)
    payload = deploy_payload(dep, req, source) | {"attempt_id": str(attempt.id)}
    await enqueue_command(db, node.id, dep.id, CommandType.DEPLOY, payload)
    await lifecycle.record_event(
        db,
        dep,
        actor=actor,
        message=f"Planned move started ({reason}): starting on another node while this one keeps serving",
        kind="migration_started",
        attempt=attempt.number,
    )
    return node


async def complete_migration(db: Session, dep: Deployment, actor: str = "worker") -> bool:
    """The standby is READY: switch traffic to it, end the old attempt, and stop the old copy after
    MIGRATION_DRAIN_SECONDS so requests in flight there can finish. Does not commit."""
    if dep.migrating_attempt_id is None or S(dep.status) not in (S.READY, S.UNHEALTHY):
        return False
    target = await db.get(DeploymentAttempt, dep.migrating_attempt_id)
    node = await db.get(Node, dep.migrating_node_id) if dep.migrating_node_id else None
    if target is None or node is None:
        return False
    old_node = dep.node_id
    await release_reservation(db, dep.id)
    await db.update_one(
        ResourceReservation, {"deployment_id": dep.id, "status": "STANDBY"}, {"$set": {"status": "ACTIVE"}}
    )
    await end_attempt(db, dep, "superseded", None, "Replaced by a planned move")
    now = utcnow()
    await db.update_one(
        DeploymentAttempt,
        {"_id": target.id},
        {"$set": {"active": True, "state": "running", "ready_at": now}},
    )
    rates = Rates.from_snapshot(target.rates) if target.rates else None
    _set_credit_source(dep, node, rates)
    fields: dict[str, Any] = {
        "node_id": node.id,
        "attempt_id": target.id,
        "migrating_attempt_id": None,
        "migrating_node_id": None,
        "migration_started_at": None,
        "schedule_attempts": dep.schedule_attempts + 1,
        "priced": dep.priced,
        "credit_provider_id": dep.credit_provider_id,
        "credit_currency": dep.credit_currency,
        "last_health_at": now,
    }
    await db.update_one(Deployment, {"_id": dep.id}, {"$set": fields})
    for k, v in fields.items():
        setattr(dep, k, v)
    message = "Planned move complete: now serving on the new node"
    if S(dep.status) == S.UNHEALTHY:
        await lifecycle.transition(
            db, dep, S.READY, actor=actor, message=message, kind="migrated", attempt=target.number
        )
    else:
        await lifecycle.record_node_change(db, dep, actor=actor, message=message, attempt=target.number)
    if old_node:
        await enqueue_command(
            db,
            old_node,
            dep.id,
            CommandType.STOP,
            {"deployment_id": str(dep.id)},
            not_before=now + timedelta(seconds=settings.MIGRATION_DRAIN_SECONDS),
        )
    await db.update_one(Node, {"_id": node.id}, {"$set": {"consecutive_failures": 0}})
    audit_service.record(
        db,
        actor_id=None,
        action="deployment.migrated",
        resource_type="deployment",
        resource_id=dep.id,
        details={"from_node": str(old_node) if old_node else None, "to_node": str(node.id)},
    )
    return True


async def abort_migration(db: Session, dep: Deployment, *, actor: str, reason: str) -> bool:
    """Cancel a planned move in progress: release the standby's capacity, end its attempt and stop it there. The
    deployment keeps running where it was. Does not commit."""
    if dep.migrating_attempt_id is None:
        return False
    target_node = dep.migrating_node_id
    await release_standby(db, dep.id)
    await db.update_one(
        DeploymentAttempt,
        {"_id": dep.migrating_attempt_id, "state": "standby"},
        {"$set": {"state": "ended", "outcome": "cancelled", "error_message": reason[:500], "ended_at": utcnow()}},
    )
    if target_node:
        if not await cancel_undelivered(db, dep.id, CommandType.DEPLOY):
            await enqueue_command(db, target_node, dep.id, CommandType.STOP, {"deployment_id": str(dep.id)})
    fields = {"migrating_attempt_id": None, "migrating_node_id": None, "migration_started_at": None}
    await db.update_one(Deployment, {"_id": dep.id}, {"$set": fields})
    for k, v in fields.items():
        setattr(dep, k, v)
    await lifecycle.record_event(
        db, dep, actor=actor, message=f"Planned move cancelled: {reason}", kind="migration_failed"
    )
    return True


async def evacuate_node(db: Session, node: Node, *, actor: str, reason: str) -> dict[str, int]:
    """Move every serving deployment off a node without interrupting them (where a replacement exists). Does not
    commit."""
    moving = staying = 0
    for dep in await db.find(Deployment, {"node_id": node.id, "status": S.READY.value}):
        if dep.migrating_attempt_id is not None or await start_migration(db, dep, actor=actor, reason=reason):
            moving += 1
        else:
            staying += 1
    return {"moving": moving, "staying": staying}


async def pause_for_credit(db: Session, dep: Deployment) -> bool:
    """Stop serving a deployment whose prepaid credit with its provider is used up. It waits (NEEDS_ATTENTION,
    CREDIT_EXHAUSTED) and is placed again automatically once a top-up is verified. Does not commit."""
    status = S(dep.status)
    if status not in (S.SCHEDULED, S.PROVISIONING, S.STARTING, S.READY, S.UNHEALTHY):
        return False
    await abort_migration(db, dep, actor="system", reason="prepaid credit is used up")
    old_node = dep.node_id
    await release_reservation(db, dep.id)
    await end_attempt(db, dep, "stopped", "CREDIT_EXHAUSTED", "Prepaid credit with this provider is used up")
    if old_node:
        await _stop_on_old_node(db, dep, old_node)
    return await lifecycle.transition(
        db,
        dep,
        S.NEEDS_ATTENTION,
        actor="system",
        message="Paused: your prepaid credit with this provider is used up. Top up to resume automatically.",
        error_code="CREDIT_EXHAUSTED",
        kind="credit_exhausted",
        node_id=None,
        priced=False,
    )


async def restart(db: Session, dep: Deployment) -> None:
    """Restart a serving deployment on its current node from the cached model. Does not commit."""
    status = S(dep.status)
    if status not in (S.READY, S.UNHEALTHY):
        raise HTTPException(
            status_code=409, detail=f"Only READY or UNHEALTHY deployments can be restarted, not {status.value}"
        )
    node = await db.get(Node, dep.node_id) if dep.node_id else None
    if node is None or node.status != NodeStatus.ONLINE or not node_is_fresh(node):
        raise HTTPException(
            status_code=409,
            detail="The node is offline. The deployment will move to another node automatically if it stays unhealthy.",
        )
    req = await requirements_for(db, dep)
    source = worker_source(await artifact_for(db, dep))
    await lifecycle.transition(
        db, dep, S.PROVISIONING, actor="customer", message="Restart requested", restart_count=dep.restart_count + 1
    )
    await enqueue_command(db, node.id, dep.id, CommandType.RESTART, deploy_payload(dep, req, source))
