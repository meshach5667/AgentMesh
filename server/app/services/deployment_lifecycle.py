"""Deployment state machine.

    REQUESTED -> SCHEDULED -> PROVISIONING -> STARTING -> READY
    READY <-> UNHEALTHY
    PROVISIONING | STARTING | UNHEALTHY -> SCHEDULED   (moved to another node; same id and endpoint)
    READY | UNHEALTHY -> PROVISIONING                  (restart on the same node)
    any non-terminal -> STOPPING -> STOPPED (was ever READY) | CANCELLED (never READY)
    any non-terminal -> FAILED

Terminal states: STOPPED, FAILED, CANCELLED. Every transition goes through ``transition``, which applies a
compare-and-set update (so two concurrent writers cannot both move the same deployment) and appends a
DeploymentEvent row.
"""

from app.core.database import Session
from app.core.timeutil import utcnow
from app.documents.deployment import Deployment, DeploymentEvent
from app.documents.deployment import DeploymentStatus as S

TERMINAL = frozenset({S.STOPPED, S.FAILED, S.CANCELLED})
ACTIVE = frozenset(set(S) - TERMINAL)
# States in which the workload may hold resources on the node.
PROVISIONED = frozenset({S.SCHEDULED, S.PROVISIONING, S.STARTING, S.READY, S.UNHEALTHY, S.STOPPING})

TRANSITIONS: dict[S, frozenset[S]] = {
    S.REQUESTED: frozenset({S.SCHEDULED, S.FAILED, S.CANCELLED}),
    S.SCHEDULED: frozenset({S.PROVISIONING, S.STARTING, S.READY, S.STOPPING, S.FAILED}),
    S.PROVISIONING: frozenset({S.SCHEDULED, S.STARTING, S.READY, S.STOPPING, S.FAILED}),
    S.STARTING: frozenset({S.SCHEDULED, S.READY, S.STOPPING, S.FAILED}),
    S.READY: frozenset({S.UNHEALTHY, S.PROVISIONING, S.STOPPING, S.FAILED}),
    S.UNHEALTHY: frozenset({S.READY, S.SCHEDULED, S.PROVISIONING, S.STOPPING, S.FAILED}),
    S.STOPPING: frozenset({S.STOPPED, S.CANCELLED, S.FAILED}),
    S.STOPPED: frozenset(),
    S.FAILED: frozenset(),
    S.CANCELLED: frozenset(),
}


class InvalidTransition(Exception):  # noqa: N818
    pass


def can_transition(current: str, new: str) -> bool:
    return S(new) in TRANSITIONS[S(current)]


async def transition(
    db: Session,
    deployment: Deployment,
    new: S,
    *,
    actor: str,
    message: str | None = None,
    error_code: str | None = None,
    **fields,
) -> bool:
    """Move ``deployment`` to ``new``. Returns False (and changes nothing) if another writer changed the
    status first. Raises InvalidTransition for transitions the state machine forbids. Does not commit."""
    current = S(deployment.status)
    if new == current:
        return True
    if not can_transition(current, new):
        raise InvalidTransition(f"{current.value} -> {new.value} is not allowed")

    now = utcnow()
    values: dict = {"status": new.value, "updated_at": now, **fields}
    if new == S.READY:
        values.setdefault("ready_at", now)
        values["was_ready"] = True
        values["error_code"] = None
        values["error_message"] = None
    if new in TERMINAL:
        values.setdefault("ended_at", now)
    if error_code:
        values["error_code"] = error_code
        values["error_message"] = message

    if not await db.update_one(Deployment, {"_id": deployment.id, "status": current.value}, {"$set": values}):
        return False
    for key, value in values.items():
        setattr(deployment, key, value)
    db.add(
        DeploymentEvent(
            deployment_id=deployment.id,
            from_status=current.value,
            to_status=new.value,
            actor=actor,
            message=message,
            node_id=deployment.node_id,
        )
    )
    return True


async def record_event(db: Session, deployment: Deployment, *, actor: str, message: str) -> None:
    """Progress note without a state change (e.g. model download percentage)."""
    db.add(DeploymentEvent(deployment_id=deployment.id, from_status=None, to_status=None, actor=actor, message=message))
