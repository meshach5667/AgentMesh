"""Provider prices, quotes and cost estimates. AgentMesh processes no payments: amounts here are prices and
estimates of what customers owe providers, who are paid directly."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

PRICE = Field(ge=0, le=Decimal("1000000"), max_digits=18, decimal_places=8)
CURRENCY = Field(pattern=r"^[A-Z]{3}$", description="ISO 4217 code, e.g. NGN, USD, EUR")


class Prices(BaseModel):
    """A machine's price list: what customers pay its provider per unit."""

    model_config = ConfigDict(extra="forbid")
    currency: str = CURRENCY
    cpu_core_hour: Decimal = PRICE
    ram_gb_hour: Decimal = PRICE
    vram_gb_hour: Decimal = PRICE
    input_tokens_per_million: Decimal = PRICE
    output_tokens_per_million: Decimal = PRICE


class RatesOut(BaseModel):
    currency: str
    cpu_core_hour: Decimal
    ram_gb_hour: Decimal
    vram_gb_hour: Decimal
    input_tokens_per_million: Decimal
    output_tokens_per_million: Decimal


class NodePriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    node_id: uuid.UUID
    version: int
    currency: str
    cpu_core_hour: Decimal
    ram_gb_hour: Decimal
    vram_gb_hour: Decimal
    input_tokens_per_million: Decimal
    output_tokens_per_million: Decimal
    effective_from: datetime
    created_at: datetime


class NodePricingOut(BaseModel):
    node_id: uuid.UUID
    charging: RatesOut | None = Field(description="What the machine charges new deployments now (null: free)")
    history: list[NodePriceOut] = Field(description="The machine's price versions, newest first")


class DefaultPricesIn(Prices):
    apply_to_existing: bool = Field(False, description="Also publish these prices on every active machine")


class DefaultPricesOut(BaseModel):
    prices: Prices | None = Field(description="Prices new machines start with (null: new machines are free)")
    updated_machines: int = 0


class PriceRange(BaseModel):
    min: Decimal
    max: Decimal


class CurrencyMarket(BaseModel):
    currency: str
    nodes: int
    ranges: dict[str, PriceRange]


class MarketOut(BaseModel):
    nodes: int = Field(description="Machines that can take work now")
    free_nodes: int = Field(description="How many of them are free to use")
    currencies: list[CurrencyMarket] = Field(description="Price ranges of the priced ones, per currency")


class RuntimeQuote(BaseModel):
    runtime: str
    requirements: dict
    eligible_nodes: int = Field(description="Machines that fit and are within the price limits")
    over_price_limit: int = Field(description="Machines that fit but charge more than the limits")
    other_currency: int = Field(description="Machines that fit but are priced in another currency")
    cheapest: RatesOut | None = Field(description="Rates of the machine placement would pick now (null: free)")
    hourly: Decimal | None = Field(description="Hourly price of the reservation on that machine (null: no machine)")
    provider: dict | None = Field(description="Who runs that machine and how they take payment")


class QuoteOut(BaseModel):
    currency: str
    by_runtime: list[RuntimeQuote]


class DeploymentPricingOut(BaseModel):
    deployment_id: uuid.UUID
    rates: RatesOut | None = Field(description="What the deployment is estimated at now on its machine (null: free)")
    hourly: Decimal | None = Field(description="Hourly price of its reservation at those rates")
    placed_at: dict[str, str] | None = Field(description="Rates when it was placed: the most it is estimated at there")
    provider: dict | None = Field(description="Who runs its machine and how to pay them")
    payment_reference: str = Field(description="Quote this when paying the provider; it matches their estimates")


class CostEstimateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    deployment_id: uuid.UUID
    node_id: uuid.UUID | None
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
    currency: str
    rates: dict[str, str] | None = None
    created_at: datetime
    customer_id: uuid.UUID | None = Field(None, exclude=True)
    provider_id: uuid.UUID | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def customer_ref(self) -> str | None:
        """Short customer reference a provider can match against a payment (never the account's identity)."""
        return str(self.customer_id)[:8].upper() if self.customer_id else None


class CostTotal(BaseModel):
    currency: str
    amount: Decimal
    resource_amount: Decimal
    token_amount: Decimal
    ready_hours: float


class CostDay(BaseModel):
    day: str
    currency: str
    amount: Decimal
    deployments: int


class CostSummaryOut(BaseModel):
    scope: str
    days: int
    since: datetime
    totals: list[CostTotal]
    by_day: list[CostDay]
