"""Pricing, rated charges, Paystack payments (top-ups), webhook inbox, and provider payouts.

Measured usage (usage_records, deployment lifecycle events) is kept separate from what is charged: a Charge
records the quantities it priced, the pricing version used, and the ledger amounts it produced.
"""

import enum
import uuid
from datetime import datetime

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import ZERO, Doc, Money, index, unique


class PricingRule(Doc):
    """One immutable price list version. The active rule is the newest whose effective_from has passed."""

    version: int
    currency: str
    cpu_core_hour: Money = ZERO
    ram_gb_hour: Money = ZERO
    vram_gb_hour: Money = ZERO
    input_tokens_per_million: Money = ZERO
    output_tokens_per_million: Money = ZERO
    platform_fee_rate: Money
    effective_from: datetime
    notes: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "pricing_rules"
        indexes = [unique("version", name="uq_pricing_rules_version"), index("effective_from")]


class NodePrice(Doc):
    """One immutable version of a node's own price list, set by its provider. The node charges the newest version
    whose effective_from has passed; a node without one charges the network prices (PricingRule)."""

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


class Charge(Doc):
    """What a deployment was charged for one billing window on one node, priced with one pricing version."""

    deployment_id: uuid.UUID
    node_id: uuid.UUID | None = None
    customer_wallet_id: uuid.UUID
    provider_wallet_id: uuid.UUID | None = None
    # Network price version in force (it sets the commission; null if none was set). node_price_id is the node's own
    # price version when it had one, and rates the unit prices actually applied.
    pricing_rule_id: uuid.UUID | None = None
    node_price_id: uuid.UUID | None = None
    rates: dict[str, str] | None = None
    period_start: datetime
    period_end: datetime
    # Measured quantities (snapshot): READY time from lifecycle events, reservation from the scheduler,
    # tokens as reported by the runtime.
    ready_seconds: float = 0
    cpu_cores: int = 0
    ram_mb: int = 0
    vram_mb: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    resource_amount: Money
    token_amount: Money
    amount: Money
    provider_amount: Money
    platform_fee: Money
    # Commission rate of the pricing version, kept with the charge so its split can always be explained. A charge
    # for a node without a provider account keeps the whole amount as platform_fee.
    platform_fee_rate: Money | None = None
    # Refunded so far (see Refund): the total, and how much of it came from the commission and the provider's share.
    refunded_amount: Money = ZERO
    refunded_fee: Money = ZERO
    refunded_provider: Money = ZERO
    currency: str
    created_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "charges"
        indexes = [
            unique("deployment_id", "node_id", "period_start", name="uq_charges_deployment_node_period"),
            index("node_id"),
            index("customer_wallet_id"),
            index("provider_wallet_id"),
            index("created_at"),
        ]


class PaymentStatus(str, enum.Enum):  # noqa: UP042
    INITIALIZED = "INITIALIZED"  # checkout created, customer has not paid (yet)
    SUCCEEDED = "SUCCEEDED"  # verified and credited exactly once
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"
    REVIEW = "REVIEW"  # Paystack reported success but amount/currency did not match; not credited


class Payment(Doc):
    """A customer top-up through Paystack. Credited to the wallet only once, on verified success."""

    user_id: uuid.UUID
    wallet_id: uuid.UUID
    provider: str = "paystack"
    reference: str
    amount: Money
    currency: str
    status: str = PaymentStatus.INITIALIZED.value
    provider_status: str | None = None
    authorization_url: str | None = None
    channel: str | None = None
    failure_reason: str | None = None
    transaction_id: uuid.UUID | None = None
    paid_at: datetime | None = None
    verified_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "payments"
        indexes = [unique("reference", name="uq_payments_reference"), index("user_id"), index("status")]


class PaymentEvent(Doc):
    """Webhook inbox. The unique event_key makes redelivered webhooks no-ops. Payloads are not stored (they
    contain customer contact and card details); only what is needed to trace processing."""

    provider: str
    event_key: str
    event_type: str
    reference: str | None = None
    outcome: str | None = None
    received_at: datetime = Field(default_factory=utcnow)
    processed_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "payment_events"
        indexes = [unique("event_key", name="uq_payment_events_event_key"), index("reference")]


class PayoutAccount(Doc):
    """A provider's Paystack transfer recipient. Only the last four digits of the account are kept."""

    user_id: uuid.UUID
    provider: str = "paystack"
    recipient_code: str
    bank_code: str
    bank_name: str | None = None
    account_name: str | None = None
    account_last4: str
    currency: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "payout_accounts"
        indexes = [unique("user_id", name="uq_payout_accounts_user_id")]


class PayoutStatus(str, enum.Enum):  # noqa: UP042
    REQUESTED = "REQUESTED"  # funds held; waiting for operator approval
    PENDING = "PENDING"  # transfer initiated (or outcome unknown); waiting for Paystack
    OTP_REQUIRED = "OTP_REQUIRED"  # Paystack wants an OTP; the operator must finalize or disable OTP
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"  # funds returned to the wallet
    REVERSED = "REVERSED"  # funds returned to the wallet
    REJECTED = "REJECTED"  # declined by an operator; funds returned


class Payout(Doc):
    user_id: uuid.UUID
    wallet_id: uuid.UUID
    payout_account_id: uuid.UUID
    amount: Money
    currency: str
    reference: str
    status: str = PayoutStatus.REQUESTED.value
    transfer_code: str | None = None
    failure_reason: str | None = None
    transaction_id: uuid.UUID | None = None
    decided_by: uuid.UUID | None = None
    decided_at: datetime | None = None
    completed_at: datetime | None = None
    # Set when reconciliation confirmed Paystack's record of the transfer matches ours.
    reconciled_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "payouts"
        indexes = [unique("reference", name="uq_payouts_reference"), index("user_id"), index("status")]


class RefundKind(str, enum.Enum):  # noqa: UP042
    CHARGE = "charge"  # a compute charge credited back to the wallet (commission and provider share reversed)
    TOPUP = "topup"  # wallet funds sent back to the customer's card through Paystack


class RefundStatus(str, enum.Enum):  # noqa: UP042
    PENDING = "PENDING"  # top-up refund: funds held, waiting for Paystack
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"  # held funds returned to the wallet


class Refund(Doc):
    """A refund issued by an operator. Charge refunds settle at once; top-up refunds hold the amount (a PENDING
    ledger debit) until Paystack reports the refund processed or failed."""

    kind: str
    reference: str
    user_id: uuid.UUID  # the customer
    wallet_id: uuid.UUID
    charge_id: uuid.UUID | None = None
    payment_id: uuid.UUID | None = None
    provider_wallet_id: uuid.UUID | None = None
    amount: Money
    provider_amount: Money = ZERO  # taken back from the provider (charge refunds)
    platform_fee: Money = ZERO  # commission given back (charge refunds)
    currency: str
    reason: str
    status: str = RefundStatus.PENDING.value
    paystack_refund_id: str | None = None
    provider_status: str | None = None
    failure_reason: str | None = None
    transaction_id: uuid.UUID | None = None  # the hold, for top-up refunds
    requested_by: uuid.UUID
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "refunds"
        indexes = [
            unique("reference", name="uq_refunds_reference"),
            # At most one top-up refund in flight per payment, so Paystack's refund events match it unambiguously.
            unique(
                "payment_id",
                name="uq_refunds_open_topup",
                where={"kind": RefundKind.TOPUP.value, "status": RefundStatus.PENDING.value},
            ),
            index("user_id"),
            index("charge_id"),
            index("status"),
            index("created_at"),
        ]
