import logging
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services.wallet_service import get_or_create_wallet

logger = logging.getLogger(__name__)

PLATFORM_FEE_RATE = Decimal("0.10")


async def settle_usage(
    db: AsyncSession, deployment_id: uuid.UUID, customer_id: uuid.UUID, provider_id: uuid.UUID, total_cost: Decimal
):
    """
    Settle usage by calculating cost, charging customer, crediting provider 90%,
    and taking a 10% platform fee.
    """
    if total_cost <= 0:
        return None

    # Get or create wallets
    customer_wallet = await get_or_create_wallet(db, customer_id)
    provider_wallet = await get_or_create_wallet(db, provider_id)

    # Calculate splits
    platform_fee = total_cost * PLATFORM_FEE_RATE
    provider_credit = total_cost - platform_fee

    # Check balance
    if customer_wallet.balance < total_cost:
        raise HTTPException(status_code=400, detail="Insufficient funds for usage settlement")

    try:
        # Charge customer
        customer_wallet.balance -= total_cost
        charge_tx = Transaction(
            from_wallet=customer_wallet.id,
            amount=total_cost,
            type=TransactionType.COMPUTE_CHARGE,
            status=TransactionStatus.SETTLED,
            deployment_id=deployment_id,
            description=f"Charge for deployment {deployment_id}",
        )
        db.add(charge_tx)

        # Credit provider
        provider_wallet.balance += provider_credit
        credit_tx = Transaction(
            to_wallet=provider_wallet.id,
            amount=provider_credit,
            type=TransactionType.PROVIDER_CREDIT,
            status=TransactionStatus.SETTLED,
            deployment_id=deployment_id,
            description=f"Earnings from deployment {deployment_id}",
        )
        db.add(credit_tx)

        # Platform fee transaction (system wallet would receive this, omit for now)
        fee_tx = Transaction(
            from_wallet=customer_wallet.id,
            amount=platform_fee,
            type=TransactionType.PLATFORM_FEE,
            status=TransactionStatus.SETTLED,
            deployment_id=deployment_id,
            description=f"Platform fee for deployment {deployment_id}",
        )
        db.add(fee_tx)

        await db.commit()
        return charge_tx
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to settle usage: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process payment settlement")
