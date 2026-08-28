from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_action(db: AsyncSession, user_id: str, action: str, resource_type: str, resource_id: str, details: dict):
    log = AuditLog(
        user_id=user_id, action=action, resource_type=resource_type, resource_id=resource_id, details=details
    )
    db.add(log)
    await db.commit()
