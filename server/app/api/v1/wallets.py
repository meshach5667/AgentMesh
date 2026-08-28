from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user

router = APIRouter()


class DepositRequest(BaseModel):
    amount: float


@router.get("")
async def get_wallet(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return {"balance": 0, "currency": "USD"}


@router.post("/deposit")
async def deposit(req: DepositRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return {"status": "success"}
