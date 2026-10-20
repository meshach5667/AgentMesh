"""Periodic reconciliation. Each ``run_*`` function is a single pass and is safe to run repeatedly."""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.database import session_scope
from app.models.deployment import Deployment
from app.models.deployment import DeploymentStatus as S
from app.models.node import Node, NodeStatus
from app.models.worker import CommandStatus, CommandType, NodeCommand
from app.services import deployment_lifecycle as lifecycle
from app.services import worker_service
from app.services.scheduler_service import release_reservation

logger = logging.getLogger(__name__)

PROVISIONING_STATES = (S.SCHEDULED.value, S.PROVISIONING.value, S.STARTING.value)


async def _fail(db, dep: Deployment, code: str, message: str, *, cleanup: bool) -> None:
    if await lifecycle.transition(db, dep, S.FAILED, actor="system", message=message, error_code=code):
        await release_reservation(db, dep.id)
        if cleanup and dep.node_id:
            dep.cleanup_status = "pending"
            await worker_service.enqueue_command(
                db, dep.node_id, dep.id, CommandType.STOP, {"deployment_id": str(dep.id)}
            )


async def run_stale_nodes(now: datetime | None = None) -> int:
    """Mark nodes without a recent heartbeat OFFLINE and their serving deployments UNHEALTHY. Reservations
    are kept: a brief disconnection must not let the scheduler double-book the node."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(seconds=settings.HEARTBEAT_TIMEOUT_SECONDS)
    async with session_scope() as db:
        nodes = (
            (
                await db.execute(
                    select(Node).where(
                        Node.status == NodeStatus.ONLINE.value,
                        Node.mode.is_not(None),
                        Node.last_heartbeat < cutoff,
                    )
                )
            )
            .scalars()
            .all()
        )
        for node in nodes:
            node.status = NodeStatus.OFFLINE.value
            deps = (
                (
                    await db.execute(
                        select(Deployment).where(Deployment.node_id == node.id, Deployment.status == S.READY.value)
                    )
                )
                .scalars()
                .all()
            )
            for dep in deps:
                await lifecycle.transition(
                    db, dep, S.UNHEALTHY, actor="system", message="Node stopped sending heartbeats"
                )
        await db.commit()
        return len(nodes)


async def run_deployment_timeouts(now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    changed = 0
    async with session_scope() as db:
        deps = (await db.execute(select(Deployment).where(Deployment.status.in_(PROVISIONING_STATES)))).scalars().all()
        for dep in deps:
            last_progress = dep.updated_at or dep.created_at
            if now - dep.created_at > timedelta(seconds=settings.PROVISION_MAX_SECONDS):
                await _fail(
                    db, dep, "PROVISION_TIMEOUT", "Provisioning exceeded the maximum allowed time", cleanup=True
                )
                changed += 1
            elif now - last_progress > timedelta(seconds=settings.PROVISION_STALL_TIMEOUT_SECONDS):
                await _fail(db, dep, "PROVISION_STALLED", "No provisioning progress reported by the node", cleanup=True)
                changed += 1

        stopping = (await db.execute(select(Deployment).where(Deployment.status == S.STOPPING.value))).scalars().all()
        for dep in stopping:
            if now - (dep.updated_at or dep.created_at) > timedelta(seconds=settings.STOP_TIMEOUT_SECONDS):
                final = S.STOPPED if dep.was_ready else S.CANCELLED
                msg = "Stop not confirmed by the node; it will be told to clean up when it reconnects"
                if await lifecycle.transition(db, dep, final, actor="system", message=msg):
                    dep.cleanup_status = "pending_node"
                    await release_reservation(db, dep.id)
                    changed += 1

        unhealthy = (await db.execute(select(Deployment).where(Deployment.status == S.UNHEALTHY.value))).scalars().all()
        for dep in unhealthy:
            if now - (dep.updated_at or dep.created_at) > timedelta(seconds=settings.UNHEALTHY_GRACE_SECONDS):
                await _fail(db, dep, "UNHEALTHY_TIMEOUT", "Deployment stayed unhealthy too long", cleanup=True)
                changed += 1
        await db.commit()
    return changed


async def run_command_leases(now: datetime | None = None) -> int:
    """Give up on commands whose final lease expired. A DEPLOY that was never acknowledged fails its
    deployment; a STOP that was never acknowledged is left to the stop timeout above."""
    now = now or datetime.utcnow()
    async with session_scope() as db:
        cmds = (
            (
                await db.execute(
                    select(NodeCommand).where(
                        NodeCommand.status == CommandStatus.LEASED.value,
                        NodeCommand.lease_expires_at < now,
                        NodeCommand.attempts >= NodeCommand.max_attempts,
                    )
                )
            )
            .scalars()
            .all()
        )
        for cmd in cmds:
            cmd.status = CommandStatus.FAILED.value
            cmd.error = "Lease expired after maximum delivery attempts"
            cmd.completed_at = now
            if cmd.type == CommandType.DEPLOY.value and cmd.deployment_id:
                dep = await db.get(Deployment, cmd.deployment_id)
                if dep and dep.status in PROVISIONING_STATES:
                    await _fail(
                        db, dep, "NODE_UNRESPONSIVE", "The node did not acknowledge the deployment", cleanup=False
                    )
        await db.commit()
        return len(cmds)


async def monitor_loop() -> None:
    while True:
        await asyncio.sleep(settings.MONITOR_INTERVAL_SECONDS)
        for job in (run_stale_nodes, run_command_leases, run_deployment_timeouts):
            try:
                await job()
            except Exception:  # noqa: BLE001
                logger.exception("Background job %s failed", job.__name__)
