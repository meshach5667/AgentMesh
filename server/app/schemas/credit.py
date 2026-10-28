import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.schemas.provider import safe_text


class TopupIn(BaseModel):
    """Buy prepaid credit with a provider: through the provider's own gateway account, or by a method the provider
    confirms by hand (give the reference of your transfer)."""

    model_config = ConfigDict(extra="forbid")
    provider_id: uuid.UUID
    amount: Decimal = Field(gt=0, le=Decimal("1000000000"), max_digits=14, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    method: Literal["gateway", "manual"]
    gateway: Literal["paystack", "flutterwave", "stripe"] | None = None
    reference: str | None = Field(default=None, min_length=3, max_length=100, pattern=r"^[A-Za-z0-9 ._/#:-]+$")
    note: str | None = Field(default=None, max_length=300)

    def model_post_init(self, __context) -> None:
        self.note = safe_text(self.note)


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accept: bool
    reason: str | None = Field(default=None, max_length=300)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    customer_id: uuid.UUID = Field(exclude=True)
    provider_id: uuid.UUID
    method: str
    gateway: str | None
    amount: Decimal
    currency: str
    reference: str
    checkout_url: str | None
    state: str
    gateway_status: str | None
    note: str | None
    reason: str | None
    verified_at: datetime | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def customer_ref(self) -> str:
        return str(self.customer_id)[:8].upper()


class BalanceOut(BaseModel):
    provider_id: uuid.UUID
    provider: str
    currency: str
    balance: Decimal
    customer_ref: str | None = None


class CreditsOut(BaseModel):
    balances: list[BalanceOut]
    payments: list[PaymentOut]


class GatewayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    secret_key: str = Field(min_length=16, max_length=300, pattern=r"^[A-Za-z0-9_-]+$")


class GatewayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    gateway: str
    key_hint: str
    mode: str
    verified_at: datetime | None
