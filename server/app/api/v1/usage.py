from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

router = APIRouter()

@router.get("/{deployment_id}")
async def get_usage(deployment_id: str, db: AsyncSession = Depends(get_db)):
    return []
