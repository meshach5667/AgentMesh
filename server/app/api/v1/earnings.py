from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.wallet import Wallet
from app.schemas.earnings import EarningsSummary

router = APIRouter()

@router.get("", response_model=EarningsSummary)
async def get_earnings(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
    wallet = result.scalars().first()
    if not wallet:
        return EarningsSummary(
            total_earnings=0,
            pending_earnings=0,
            available_balance=0,
            total_deployments=0,
            active_deployments=0,
        )

    # Total settled provider credits
    settled = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.to_wallet == wallet.id,
            Transaction.type == TransactionType.PROVIDER_CREDIT,
            Transaction.status == TransactionStatus.SETTLED,
        )
    )
    total_earnings = settled.scalar() or 0

    # Pending
    pending = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.to_wallet == wallet.id,
            Transaction.type == TransactionType.PROVIDER_CREDIT,
            Transaction.status == TransactionStatus.PENDING,
        )
    )
    pending_earnings = pending.scalar() or 0

    return EarningsSummary(
        total_earnings=total_earnings,
        pending_earnings=pending_earnings,
        available_balance=wallet.balance,
        total_deployments=0,
        active_deployments=0
    )

@router.get("/history")
async def get_history(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
    wallet = result.scalars().first()
    if not wallet:
        return []
    result = await db.execute(
        select(Transaction)
        .filter(Transaction.to_wallet == wallet.id, Transaction.type == TransactionType.PROVIDER_CREDIT)
        .order_by(Transaction.created_at.desc())
    )
    return result.scalars().all()
