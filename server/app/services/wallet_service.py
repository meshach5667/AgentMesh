import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.wallet import Wallet


async def get_or_create_wallet(db: AsyncSession, user_id: uuid.UUID):
    result = await db.execute(select(Wallet).filter(Wallet.user_id == user_id))
    wallet = result.scalars().first()
    if not wallet:
        wallet = Wallet(user_id=user_id)
        db.add(wallet)
        await db.commit()
        await db.refresh(wallet)
    return wallet


async def deposit(db: AsyncSession, user_id: uuid.UUID, amount: float):
    wallet = await get_or_create_wallet(db, user_id)
    wallet.balance += amount

    tx = Transaction(
        to_wallet=wallet.id,
        amount=amount,
        type=TransactionType.DEPOSIT,
        status=TransactionStatus.SETTLED,
        description="Deposit funds",
    )
    db.add(tx)
    await db.commit()
    return tx
