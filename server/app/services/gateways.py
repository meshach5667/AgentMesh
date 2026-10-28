"""Calls to providers' own payment gateway accounts: start a hosted checkout, and verify a transaction.

Every call uses the provider's secret key against the gateway's fixed public API host, so the money goes straight
from the customer to the provider; AgentMesh holds no gateway account of its own and takes nothing. Hosts are
constants (never taken from input), responses are parsed defensively, and keys are never logged.
"""

import logging
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GATEWAYS = ("paystack", "flutterwave", "stripe")
HOSTS = {
    "paystack": "https://api.paystack.co",
    "flutterwave": "https://api.flutterwave.com",
    "stripe": "https://api.stripe.com",
}
# Hosted checkout pages customers may be sent to (the dashboard re-checks the same list).
CHECKOUT_HOSTS = ("checkout.paystack.com", "checkout.flutterwave.com", "checkout.stripe.com")
# Currencies Stripe charges in whole units (https://docs.stripe.com/currencies#zero-decimal).
ZERO_DECIMAL = {
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "JPY",
    "KMF",
    "KRW",
    "MGA",
    "PYG",
    "RWF",
    "UGX",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
}
TIMEOUT = 20.0

# Tests replace this with an httpx.MockTransport; production uses the default network transport.
transport: httpx.AsyncBaseTransport | None = None


class GatewayError(Exception):
    """The gateway refused the request or could not be reached. The message is safe to show."""


@dataclass(frozen=True)
class Checkout:
    url: str
    gateway_ref: str | None


@dataclass(frozen=True)
class Verification:
    paid: bool  # the gateway reports a completed, successful payment
    failed: bool  # the gateway reports it failed or was abandoned (no point checking again)
    amount: Decimal | None
    currency: str | None
    status: str


def key_mode(gateway: str, secret: str) -> str | None:
    """'test' or 'live' for a well-formed secret key of this gateway, else None."""
    prefixes = {
        "paystack": (("sk_test_", "test"), ("sk_live_", "live")),
        "stripe": (("sk_test_", "test"), ("sk_live_", "live"), ("rk_test_", "test"), ("rk_live_", "live")),
        "flutterwave": (("FLWSECK_TEST-", "test"), ("FLWSECK-", "live")),
    }
    for prefix, mode in prefixes.get(gateway, ()):
        if secret.startswith(prefix) and len(secret) > len(prefix) + 8:
            return mode
    return None


def minor_units(amount: Decimal, currency: str) -> int:
    factor = 1 if currency.upper() in ZERO_DECIMAL else 100
    return int((amount * factor).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def from_minor(value: Any, currency: str) -> Decimal:
    factor = 1 if currency.upper() in ZERO_DECIMAL else 100
    return (Decimal(str(value)) / factor).quantize(Decimal("0.01"))


async def _request(gateway: str, method: str, path: str, secret: str, **kwargs) -> dict:
    headers = {"Authorization": f"Bearer {secret}"}
    try:
        async with httpx.AsyncClient(base_url=HOSTS[gateway], timeout=TIMEOUT, transport=transport) as client:
            resp = await client.request(method, path, headers=headers, **kwargs)
    except httpx.HTTPError as exc:
        raise GatewayError(f"Could not reach {gateway}: {type(exc).__name__}") from None
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code >= 400:
        message = body.get("message") or (body.get("error") or {}).get("message") or f"HTTP {resp.status_code}"
        raise GatewayError(f"{gateway} refused the request: {str(message)[:200]}")
    return body if isinstance(body, dict) else {}


async def check_key(gateway: str, secret: str) -> None:
    """Raise GatewayError unless the key authenticates with the gateway (a harmless read-only call)."""
    path = {"paystack": "/balance", "flutterwave": "/v3/balances", "stripe": "/v1/balance"}[gateway]
    await _request(gateway, "GET", path, secret)


async def start_checkout(
    gateway: str, secret: str, *, reference: str, amount: Decimal, currency: str, email: str, return_url: str
) -> Checkout:
    if gateway == "paystack":
        body = await _request(
            gateway,
            "POST",
            "/transaction/initialize",
            secret,
            json={
                "email": email,
                "amount": minor_units(amount, currency),
                "currency": currency,
                "reference": reference,
                "callback_url": return_url,
            },
        )
        url = (body.get("data") or {}).get("authorization_url")
        ref = None
    elif gateway == "flutterwave":
        body = await _request(
            gateway,
            "POST",
            "/v3/payments",
            secret,
            json={
                "tx_ref": reference,
                "amount": str(amount),
                "currency": currency,
                "redirect_url": return_url,
                "customer": {"email": email},
            },
        )
        url = (body.get("data") or {}).get("link")
        ref = None
    else:
        body = await _request(
            gateway,
            "POST",
            "/v1/checkout/sessions",
            secret,
            data={
                "mode": "payment",
                "success_url": return_url,
                "cancel_url": return_url,
                "client_reference_id": reference,
                "customer_email": email,
                "metadata[reference]": reference,
                "line_items[0][quantity]": "1",
                "line_items[0][price_data][currency]": currency.lower(),
                "line_items[0][price_data][unit_amount]": str(minor_units(amount, currency)),
                "line_items[0][price_data][product_data][name]": "AgentMesh compute credit",
            },
        )
        url = body.get("url")
        ref = body.get("id")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise GatewayError(f"{gateway} did not return a checkout page")
    return Checkout(url=url, gateway_ref=ref if isinstance(ref, str) else None)


async def verify(gateway: str, secret: str, *, reference: str, gateway_ref: str | None) -> Verification:
    """Ask the provider's gateway what happened to this payment."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,100}", reference):
        return Verification(False, True, None, None, "invalid_reference")
    if gateway == "paystack":
        data = (await _request(gateway, "GET", f"/transaction/verify/{reference}", secret)).get("data") or {}
        status = str(data.get("status") or "unknown")
        if data.get("reference") not in (None, reference):
            return Verification(False, True, None, None, "reference_mismatch")
        currency = str(data.get("currency") or "").upper() or None
        amount = from_minor(data["amount"], currency or "") if data.get("amount") is not None else None
        return Verification(
            status == "success", status in ("failed", "abandoned", "reversed"), amount, currency, status
        )
    if gateway == "flutterwave":
        data = (
            await _request(gateway, "GET", "/v3/transactions/verify_by_reference", secret, params={"tx_ref": reference})
        ).get("data") or {}
        status = str(data.get("status") or "unknown")
        if data.get("tx_ref") not in (None, reference):
            return Verification(False, True, None, None, "reference_mismatch")
        amount = Decimal(str(data["amount"])).quantize(Decimal("0.01")) if data.get("amount") is not None else None
        currency = str(data.get("currency") or "").upper() or None
        return Verification(status == "successful", status in ("failed", "cancelled"), amount, currency, status)
    if not gateway_ref or not re.fullmatch(r"cs_[A-Za-z0-9_]{8,200}", gateway_ref):
        return Verification(False, True, None, None, "missing_session")
    data = await _request(gateway, "GET", f"/v1/checkout/sessions/{gateway_ref}", secret)
    status = str(data.get("payment_status") or "unknown")
    if data.get("client_reference_id") not in (None, reference):
        return Verification(False, True, None, None, "reference_mismatch")
    currency = str(data.get("currency") or "").upper() or None
    amount = from_minor(data["amount_total"], currency or "") if data.get("amount_total") is not None else None
    return Verification(status == "paid", data.get("status") == "expired", amount, currency, status)
