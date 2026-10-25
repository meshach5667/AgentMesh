from fastapi import APIRouter, Depends

from app.core.database import Session, get_db
from app.core.dependencies import get_current_user
from app.documents.transaction import Transaction
from app.documents.wallet import Wallet
from app.schemas.transaction import TransactionResponse

router = APIRouter()


@router.get("", response_model=list[TransactionResponse])
async def list_transactions(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    wallet = await db.find_one(Wallet, {"user_id": current_user.id})
    if not wallet:
        return []
    return await db.find(
        Transaction, {"$or": [{"from_wallet": wallet.id}, {"to_wallet": wallet.id}]}, sort=[("created_at", -1)]
    )
