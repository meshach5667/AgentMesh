import uuid
from datetime import datetime

from pydantic import Field

from app.core.config import settings
from app.core.timeutil import utcnow
from app.documents.base import ZERO, Doc, Money, unique


class Wallet(Doc):
    user_id: uuid.UUID | None = None
    balance: Money | None = ZERO
    currency: str | None = Field(default_factory=lambda: settings.BILLING_CURRENCY)
    created_at: datetime | None = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "wallets"
        indexes = [unique("user_id", name="uq_wallets_user_id")]
