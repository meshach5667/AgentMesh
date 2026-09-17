import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


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


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_wallet = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=True)
    to_wallet = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=True)
    amount = Column(Numeric(18, 8), nullable=False)
    type = Column(Enum(TransactionType))
    status = Column(Enum(TransactionStatus))
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id"), nullable=True)
    reference = Column(String(255))
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
