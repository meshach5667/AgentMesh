import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

PRICE = Field(ge=0, le=Decimal("1000000"), max_digits=18, decimal_places=8)


class PricingRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cpu_core_hour: Decimal = PRICE
    ram_gb_hour: Decimal = PRICE
    vram_gb_hour: Decimal = PRICE
    input_tokens_per_million: Decimal = PRICE
    output_tokens_per_million: Decimal = PRICE
    platform_fee_rate: Decimal | None = Field(
        None, ge=0, lt=1, max_digits=5, decimal_places=4, description="Share kept by the platform; default 0.10"
    )
    effective_from: datetime | None = Field(None, description="UTC; defaults to now. Cannot be in the past")
    notes: str | None = Field(None, max_length=500)


class CommissionChange(BaseModel):
    """A new pricing version with the prices in force and another platform commission."""

    model_config = ConfigDict(extra="forbid")
    platform_fee_rate: Decimal = Field(ge=0, lt=1, max_digits=5, decimal_places=4)
    effective_from: datetime | None = Field(None, description="UTC; defaults to now. Cannot be in the past")
    notes: str | None = Field(None, max_length=500)


class PricingRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int
    currency: str
    cpu_core_hour: Decimal
    ram_gb_hour: Decimal
    vram_gb_hour: Decimal
    input_tokens_per_million: Decimal
    output_tokens_per_million: Decimal
    platform_fee_rate: Decimal
    effective_from: datetime
    notes: str | None
    created_at: datetime


class PricingOut(BaseModel):
    current: PricingRuleOut | None
    upcoming: list[PricingRuleOut]
    currency: str
    min_prepaid_hours: float
    billing_interval_seconds: int
    default_platform_fee_rate: Decimal
    max_platform_fee_rate: Decimal


class ChargeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    deployment_id: uuid.UUID
    node_id: uuid.UUID | None
    pricing_rule_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    ready_seconds: float
    cpu_cores: int
    ram_mb: int
    vram_mb: int
    input_tokens: int
    output_tokens: int
    resource_amount: Decimal
    token_amount: Decimal
    amount: Decimal
    provider_amount: Decimal
    platform_fee: Decimal
    # The commission rate this charge was split at (null on charges made before it was recorded).
    platform_fee_rate: Decimal | None = None
    refunded_amount: Decimal = Decimal(0)
    currency: str
    created_at: datetime


class ChargeTotals(BaseModel):
    charges: int
    gross: Decimal = Field(description="What customers were charged")
    platform_fee: Decimal = Field(description="Platform commission")
    provider_share: Decimal = Field(description="Credited to node providers")
    resource_amount: Decimal
    token_amount: Decimal
    effective_fee_rate: Decimal | None = Field(description="platform_fee / gross; null when nothing was charged")


class BillingSummary(BaseModel):
    scope: str  # customer | provider | network
    days: int
    since: datetime
    currency: str
    totals: ChargeTotals


class TopupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    reference: str
    amount: Decimal
    currency: str
    status: str
    provider_status: str | None
    authorization_url: str | None
    channel: str | None
    failure_reason: str | None
    paid_at: datetime | None
    created_at: datetime


class PayoutAccountSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_number: str = Field(pattern=r"^\d{6,20}$")
    bank_code: str = Field(pattern=r"^[A-Za-z0-9-]{1,20}$")


class PayoutAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    bank_code: str
    bank_name: str | None
    account_name: str | None
    account_last4: str
    currency: str
    updated_at: datetime


class PayoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class PayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    amount: Decimal
    currency: str
    reference: str
    status: str
    failure_reason: str | None
    decided_at: datetime | None
    completed_at: datetime | None
    reconciled_at: datetime | None
    created_at: datetime


class PayoutDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(None, max_length=300)


class RefundCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=8, description="Default: all that is left")
    reason: str = Field(min_length=3, max_length=300, description="Shown to the customer and kept in the audit log")


class RefundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    reference: str
    user_id: uuid.UUID
    charge_id: uuid.UUID | None
    payment_id: uuid.UUID | None
    amount: Decimal
    provider_amount: Decimal
    platform_fee: Decimal
    currency: str
    reason: str
    status: str
    provider_status: str | None
    failure_reason: str | None
    created_at: datetime
    completed_at: datetime | None


class AdminTopupOut(PaymentOut):
    user_email: str | None = None
    refundable: Decimal
