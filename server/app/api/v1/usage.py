from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.usage import UsageRecord
from app.schemas.usage import UsageRecordResponse
from app.services.deployment_service import get_deployment_for_user

router = APIRouter()


@router.get("/{deployment_id}", response_model=list[UsageRecordResponse])
async def get_usage(deployment_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    deployment = await get_deployment_for_user(db, deployment_id, current_user)
    result = await db.execute(
        select(UsageRecord).filter(UsageRecord.deployment_id == deployment.id).order_by(UsageRecord.created_at.desc())
    )
    return result.scalars().all()
