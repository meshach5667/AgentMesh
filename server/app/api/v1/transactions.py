from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user

router = APIRouter()


@router.get("")
async def list_transactions(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return []
