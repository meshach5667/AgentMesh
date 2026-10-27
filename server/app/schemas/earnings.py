from decimal import Decimal

from pydantic import BaseModel


class EarningsSummary(BaseModel):
    total_earnings: Decimal
    pending_earnings: Decimal
    # From the charges for deployments the provider's nodes served: what customers paid, and the commission kept.
    gross_earnings: Decimal = Decimal(0)
    platform_fees: Decimal = Decimal(0)
    available_balance: Decimal
    total_deployments: int
    active_deployments: int
