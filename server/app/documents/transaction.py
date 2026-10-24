import enum
import uuid
from datetime import datetime

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import Doc, Money, index, unique


class TransactionType(str, enum.Enum):  # noqa: UP042
    DEPOSIT = "DEPOSIT"
    COMPUTE_CHARGE = "COMPUTE_CHARGE"
    PROVIDER_CREDIT = "PROVIDER_CREDIT"
    PLATFORM_FEE = "PLATFORM_FEE"
    REFUND = "REFUND"
    PAYOUT = "PAYOUT"


class TransactionStatus(str, enum.Enum):  # noqa: UP042
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    SETTLED = "SETTLED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


class Transaction(Doc):
    """Ledger entry. Debits (from_wallet) apply while PENDING or SETTLED; credits (to_wallet) apply only when
    SETTLED. Every wallet balance therefore equals its settled credits minus its pending and settled debits,
    which reconciliation checks. ``idempotency_key`` makes each logical posting happen at most once."""

    from_wallet: uuid.UUID | None = None
    to_wallet: uuid.UUID | None = None
    amount: Money
    type: str | None = None
    status: str | None = None
    deployment_id: uuid.UUID | None = None
    reference: str | None = None
    description: str | None = None
    created_at: datetime | None = Field(default_factory=utcnow)
    idempotency_key: str | None = None
    settled_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "transactions"
        indexes = [
            unique("idempotency_key", name="uq_transactions_idempotency_key", nullable=("idempotency_key",)),
            index("from_wallet"),
            index("to_wallet"),
            index("deployment_id"),
        ]
