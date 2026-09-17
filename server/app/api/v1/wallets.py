from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.wallet import DepositRequest, DepositResponse, WalletResponse
from app.services import wallet_service

router = APIRouter()

@router.get("", response_model=WalletResponse)
async def get_wallet(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    wallet = await wallet_service.get_or_create_wallet(db, current_user.id)
    return wallet

@router.post("/deposit", response_model=DepositResponse)
async def deposit(req: DepositRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    wallet = await wallet_service.get_or_create_wallet(db, current_user.id)
    tx = await wallet_service.deposit(db, current_user.id, float(req.amount))
    await db.refresh(wallet)
    return DepositResponse(wallet=wallet, transaction_id=tx.id, message=f"Deposited ${req.amount}")
