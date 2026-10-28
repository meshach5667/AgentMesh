"""Provider prices and the cost estimates derived from them.

AgentMesh does not process payments: customers pay providers directly, on the provider's own terms. What is kept
here is what a deployment is estimated to cost at its machines' published prices, so both sides can see it.
Measured usage (usage_records, deployment lifecycle events) stays separate from these estimates.

Collections from the retired payment system (charges, transactions, wallets, payments, payment_events, payouts,
payout_accounts, refunds, pricing_rules) are left untouched in the database as history; nothing reads or writes them.
"""

import uuid
from datetime import datetime

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import ZERO, Doc, Money, index, unique


class NodePrice(Doc):
    """One immutable version of a machine's price list, set by its provider. The machine charges the newest
    version whose effective_from has passed; a machine without one is free to use."""

    node_id: uuid.UUID
    provider_id: uuid.UUID
    version: int
    currency: str
    cpu_core_hour: Money = ZERO
    ram_gb_hour: Money = ZERO
    vram_gb_hour: Money = ZERO
    input_tokens_per_million: Money = ZERO
    output_tokens_per_million: Money = ZERO
    effective_from: datetime
    created_by: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "node_prices"
        indexes = [
            unique("node_id", "version", name="uq_node_prices_node_version"),
            index("node_id", "effective_from"),
        ]


class CostEstimate(Doc):
    """What one window of a deployment's use of one machine costs at that machine's published prices. An estimate
    of what the customer owes the provider, not a payment: AgentMesh moves no money."""

    deployment_id: uuid.UUID
    node_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    provider_id: uuid.UUID | None = None
    node_price_id: uuid.UUID | None = None
    rates: dict[str, str] | None = None  # unit prices applied, as strings
    period_start: datetime
    period_end: datetime
    # Measured quantities: READY time from lifecycle events, reservation from the scheduler, runtime-reported tokens.
    ready_seconds: float = 0
    cpu_cores: int = 0
    ram_mb: int = 0
    vram_mb: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    resource_amount: Money
    token_amount: Money
    amount: Money
    currency: str
    created_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "cost_estimates"
        indexes = [
            unique("deployment_id", "node_id", "period_start", name="uq_cost_estimates_deployment_node_period"),
            index("customer_id", "created_at"),
            index("provider_id", "created_at"),
        ]
