from pydantic import BaseModel
from decimal import Decimal
from typing import Optional
import uuid
from datetime import datetime
from enum import Enum

class TransactionTypeEnum(str, Enum):
    DEPOSIT = "DEPOSIT"
    COMPUTE_CHARGE = "COMPUTE_CHARGE"
    PROVIDER_CREDIT = "PROVIDER_CREDIT"
    PLATFORM_FEE = "PLATFORM_FEE"
    REFUND = "REFUND"
    PAYOUT = "PAYOUT"

class TransactionStatusEnum(str, Enum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    SETTLED = "SETTLED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"

class TransactionResponse(BaseModel):
    id: uuid.UUID
    from_wallet: Optional[uuid.UUID] = None
    to_wallet: Optional[uuid.UUID] = None
    amount: Decimal
    type: TransactionTypeEnum
    status: TransactionStatusEnum
    deployment_id: Optional[uuid.UUID] = None
    reference: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}

class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int
