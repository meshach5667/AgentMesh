"""Provider profiles and payment arrangements.

Customers pay providers directly. AgentMesh shows each provider's arrangement (methods, instructions, links,
terms) and processes, verifies, holds and refunds nothing. Validation keeps the arrangement safe to show: links
must be plain https to a public host, and instructions may not ask customers for secrets (PINs, one-time codes,
passwords, card details) or carry card numbers.
"""

import ipaddress
import re
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

PaymentMethod = Literal["bank_transfer", "payment_link", "mobile_money", "invoice", "other"]

# Asking a customer for any of these is never legitimate in payment instructions.
_SECRET_REQUEST = re.compile(
    r"\b(pin|otp|one[- ]time (pass)?code|passcode|password|passwd|cvv|cvc|security code|card number|"
    r"login details|seed phrase|private key)\b",
    re.IGNORECASE,
)
_DIGIT_RUN = re.compile(r"(?:\d[ -]?){13,19}")


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def safe_text(value: str | None) -> str | None:
    """Free text shown to customers: trimmed, no control characters, no requests for secrets, no card numbers."""
    if value is None:
        return None
    value = value.strip()
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError("must not contain control characters")
    if _SECRET_REQUEST.search(value):
        raise ValueError("must not ask customers for PINs, one-time codes, passwords, card details or other secrets")
    for run in _DIGIT_RUN.findall(value):
        digits = re.sub(r"\D", "", run)
        if 13 <= len(digits) <= 19 and _luhn(digits):
            raise ValueError("must not contain a payment card number")
    return value or None


def safe_url(value: str) -> str:
    """An external payment destination customers may open: https to a public host name, nothing hidden in it."""
    value = value.strip()
    if len(value) > 500 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("must be a single https URL without spaces")
    parts = urlsplit(value)
    if parts.scheme != "https":
        raise ValueError("must use https")
    if parts.username or parts.password or "@" in parts.netloc:
        raise ValueError("must not contain credentials")
    host = (parts.hostname or "").lower()
    if not host or "." not in host or host.endswith((".local", ".internal", ".localhost")) or host == "localhost":
        raise ValueError("must point to a public host name")
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        pass
    else:
        raise ValueError("must use a host name, not an IP address")
    if parts.port not in (None, 443):
        raise ValueError("must use the standard https port")
    return value


class PaymentLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=60)
    url: str

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        return safe_url(v)

    @field_validator("label")
    @classmethod
    def _label(cls, v: str) -> str:
        return safe_text(v) or "Pay"


class PaymentProfile(BaseModel):
    """How customers pay this provider. Shown to signed-in customers; never processed by AgentMesh."""

    model_config = ConfigDict(extra="forbid")
    methods: list[PaymentMethod] = Field(default_factory=list, max_length=5)
    accepted_currencies: list[str] = Field(default_factory=list, max_length=10)
    instructions: str | None = Field(default=None, max_length=2000, description="Plain text, e.g. bank and reference")
    links: list[PaymentLink] = Field(default_factory=list, max_length=5)
    terms: str | None = Field(default=None, max_length=2000, description="When payment is due, refunds, etc.")
    minimum_amount: Decimal | None = Field(
        default=None, ge=0, le=Decimal("1000000000"), max_digits=18, decimal_places=2
    )
    minimum_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    minimum_note: str | None = Field(default=None, max_length=200)

    @field_validator("accepted_currencies")
    @classmethod
    def _currencies(cls, v: list[str]) -> list[str]:
        for c in v:
            if not re.fullmatch(r"[A-Z]{3}", c):
                raise ValueError("currencies must be ISO 4217 codes such as NGN or USD")
        return sorted(set(v))

    @field_validator("instructions", "terms", "minimum_note")
    @classmethod
    def _text(cls, v: str | None) -> str | None:
        return safe_text(v)


class ProviderProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=2, max_length=60)
    description: str | None = Field(default=None, max_length=500)
    payment: PaymentProfile = Field(default_factory=lambda: PaymentProfile())

    @field_validator("display_name", "description")
    @classmethod
    def _text(cls, v: str | None) -> str | None:
        return safe_text(v)


class ProviderProfileOut(BaseModel):
    id: str
    display_name: str
    description: str | None = None
    payment: PaymentProfile | None = None


class ProviderOffer(BaseModel):
    """A provider as customers see it when choosing where to run: aggregates only, no machine is named."""

    id: str
    display_name: str
    description: str | None = None
    machines_available: int
    gpu_machines: int
    runtimes: list[str]
    free_machines: int
    prices: list[dict] = Field(description="Per currency: lowest CPU core-hour, RAM GB-hour and token prices")
    payment_methods: list[str]
    accepts_payment_arrangement: bool = Field(description="Whether the provider published how to pay them")
    gateways: list[str] = Field(
        default_factory=list, description="Gateways the provider connected: payments there are verified automatically"
    )


class ProviderDetail(ProviderOffer):
    payment: PaymentProfile | None = None
