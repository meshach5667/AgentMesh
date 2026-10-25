import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.database import Session, get_db
from app.core.dependencies import get_current_user
from app.documents.transaction import TransactionType
from app.schemas.wallet import DepositRequest, DepositResponse, WalletResponse
from app.services import audit_service, ledger_service

router = APIRouter()


@router.get("", response_model=WalletResponse)
async def get_wallet(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    wallet = await ledger_service.wallet_for_user(db, current_user.id)
    await db.commit()
    await db.refresh(wallet)
    return wallet


@router.post("/deposit", response_model=DepositResponse)
async def deposit(req: DepositRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Unpaid *test credits*, only in dev/test environments. Real top-ups go through POST /payments/topups."""
    if not settings.test_credits_enabled:
        raise HTTPException(status_code=403, detail="Test credits are only available in development environments")
    wallet = await ledger_service.wallet_for_user(db, current_user.id)
    tx = await ledger_service.post(
        db,
        key=f"test-credit:{uuid.uuid4()}",
        type=TransactionType.DEPOSIT,
        amount=req.amount,
        to_wallet=wallet,
        reference="test-credit",
        description="Test credit (unpaid, dev only)",
    )
    audit_service.record(
        db,
        actor_id=current_user.id,
        action="wallet.test_credit",
        resource_type="wallet",
        resource_id=wallet.id,
        details={"amount": str(req.amount)},
    )
    await db.commit()
    await db.refresh(wallet)
    return DepositResponse(
        wallet=WalletResponse.model_validate(wallet),
        transaction_id=tx.id,
        message=f"Added {req.amount} in test credits",
    )
