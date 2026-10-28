"""Persisted node command queue: enqueueing and cancelling. Leasing lives in worker_service."""

from app.core.config import settings
from app.core.database import Session
from app.core.timeutil import utcnow
from app.documents.worker import CommandStatus, CommandType, NodeCommand


async def enqueue_command(
    db: Session, node_id, deployment_id, type_: CommandType, payload: dict, not_before=None
) -> NodeCommand:
    """Queue a command. A STOP is not duplicated while an identical one is outstanding. Does not commit."""
    if type_ == CommandType.STOP:
        existing = await db.find_one(
            NodeCommand,
            {
                "node_id": node_id,
                "deployment_id": deployment_id,
                "type": CommandType.STOP.value,
                "status": {"$in": [CommandStatus.PENDING.value, CommandStatus.LEASED.value]},
            },
        )
        if existing:
            return existing
    cmd = NodeCommand(
        node_id=node_id,
        deployment_id=deployment_id,
        type=type_.value,
        payload=payload,
        status=CommandStatus.PENDING.value,
        attempts=0,
        max_attempts=settings.COMMAND_MAX_ATTEMPTS,
        not_before=not_before,
    )
    db.add(cmd)
    return cmd


async def cancel_undelivered(db: Session, deployment_id, type_: CommandType) -> bool:
    """Cancel a command that no worker has leased yet. Returns True if one was cancelled."""
    cancelled = await db.update_many(
        NodeCommand,
        {
            "deployment_id": deployment_id,
            "type": type_.value,
            "status": CommandStatus.PENDING.value,
            "attempts": 0,
        },
        {"$set": {"status": CommandStatus.CANCELLED.value, "completed_at": utcnow()}},
    )
    return cancelled > 0
