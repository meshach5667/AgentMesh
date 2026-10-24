import enum
import uuid
from datetime import datetime

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import ZERO, Doc, Money, unique


class UserRole(str, enum.Enum):  # noqa: UP042
    provider = "provider"
    customer = "customer"
    operator = "operator"
    admin = "admin"


class User(Doc):
    email: str
    hashed_password: str
    role: str
    is_active: bool | None = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime | None = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "users"
        indexes = [unique("email", name="uq_users_email")]


class Provider(Doc):
    user_id: uuid.UUID
    payout_status: str | None = "pending"
    balance: Money | None = ZERO
    created_at: datetime | None = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "providers"
        indexes = [unique("user_id", name="uq_providers_user_id")]


class Customer(Doc):
    user_id: uuid.UUID
    created_at: datetime | None = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "customers"
        indexes = [unique("user_id", name="uq_customers_user_id")]
