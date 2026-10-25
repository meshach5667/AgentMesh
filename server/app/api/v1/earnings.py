from decimal import Decimal

from fastapi import APIRouter, Depends

from app.core.database import Session, get_db
from app.core.dependencies import get_current_user
from app.documents.deployment import Deployment
from app.documents.transaction import Transaction, TransactionStatus, TransactionType
from app.documents.wallet import Wallet
from app.schemas.earnings import EarningsSummary
from app.schemas.transaction import TransactionResponse
from app.services.deployment_lifecycle import ACTIVE
from app.services.ledger_service import money
from app.services.reporting_service import provider_node_ids

router = APIRouter()


async def _hosted_deployments(db: Session, user_id) -> tuple[int, int]:
    """Deployments ever placed on, and currently active on, the caller's nodes."""
    on_nodes = {"node_id": {"$in": await provider_node_ids(db, user_id)}}
    total = await db.count(Deployment, on_nodes)
    active = await db.count(Deployment, {**on_nodes, "status": {"$in": [s.value for s in ACTIVE]}})
    return total, active


async def _credited(db: Session, wallet_id, status: TransactionStatus) -> Decimal:
    rows = await db.aggregate(
        Transaction,
        [
            {
                "$match": {
                    "to_wallet": wallet_id,
                    "type": TransactionType.PROVIDER_CREDIT.value,
                    "status": status.value,
                }
            },
            {"$group": {"_id": None, "amount": {"$sum": "$amount"}}},
        ],
    )
    return money(rows[0]["amount"]) if rows else Decimal(0)


@router.get("", response_model=EarningsSummary)
async def get_earnings(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    total_deployments, active_deployments = await _hosted_deployments(db, current_user.id)
    wallet = await db.find_one(Wallet, {"user_id": current_user.id})
    if not wallet:
        return EarningsSummary(
            total_earnings=Decimal(0),
            pending_earnings=Decimal(0),
            available_balance=Decimal(0),
            total_deployments=total_deployments,
            active_deployments=active_deployments,
        )

    return EarningsSummary(
        total_earnings=await _credited(db, wallet.id, TransactionStatus.SETTLED),
        pending_earnings=await _credited(db, wallet.id, TransactionStatus.PENDING),
        available_balance=Decimal(wallet.balance or 0),
        total_deployments=total_deployments,
        active_deployments=active_deployments,
    )


@router.get("/history", response_model=list[TransactionResponse])
async def get_history(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    wallet = await db.find_one(Wallet, {"user_id": current_user.id})
    if not wallet:
        return []
    return await db.find(
        Transaction,
        {"to_wallet": wallet.id, "type": TransactionType.PROVIDER_CREDIT.value},
        sort=[("created_at", -1)],
    )
