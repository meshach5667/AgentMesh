"""Prepaid credit: verified before priced service. Gateway payments are checked with the provider's own gateway
account (simulated here with httpx.MockTransport); manual payments are confirmed by the provider. Money never goes
to AgentMesh, and a payment is credited exactly once."""

import json
import uuid
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

from app.core.timeutil import utcnow
from app.documents import CreditEntry, CreditPayment, Deployment, Provider, ProviderGateway
from app.services import credit_service, gateways

PAYSTACK_KEY = "sk_test_" + "p" * 32
FLW_KEY = "FLWSECK_TEST-" + "f" * 32
STRIPE_KEY = "sk_test_" + "s" * 32
PROFILE = {
    "display_name": "Credit Provider",
    "payment": {
        "methods": ["bank_transfer"],
        "instructions": "Transfer to account 0123456789 and quote your reference.",
    },
}


class FakeGateways:
    """The three gateways' APIs, enough for checkout and verification. Records every request."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.status: dict[str, str] = {}  # reference -> gateway status
        self.amount_override: dict[str, int] = {}
        self.sessions: dict[str, dict] = {}
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            raise httpx.ConnectError("down")
        auth = request.headers.get("authorization", "")
        host, path = request.url.host, request.url.path
        if not auth.endswith(("p" * 32, "f" * 32, "s" * 32)):
            return httpx.Response(401, json={"message": "Invalid key"})
        if path in ("/balance", "/v3/balances", "/v1/balance"):
            return httpx.Response(200, json={"status": True, "data": []})
        if host == "api.paystack.co" and path == "/transaction/initialize":
            body = json.loads(request.content)
            self.sessions[body["reference"]] = body
            return httpx.Response(
                200, json={"data": {"authorization_url": f"https://checkout.paystack.com/{body['reference']}"}}
            )
        if host == "api.paystack.co" and path.startswith("/transaction/verify/"):
            ref = path.rsplit("/", 1)[1]
            body = self.sessions[ref]
            amount = self.amount_override.get(ref, body["amount"])
            return httpx.Response(
                200,
                json={
                    "data": {
                        "status": self.status.get(ref, "ongoing"),
                        "reference": ref,
                        "amount": amount,
                        "currency": body["currency"],
                    }
                },
            )
        if host == "api.flutterwave.com" and path == "/v3/payments":
            body = json.loads(request.content)
            self.sessions[body["tx_ref"]] = body
            return httpx.Response(
                200, json={"data": {"link": f"https://checkout.flutterwave.com/pay/{body['tx_ref']}"}}
            )
        if host == "api.flutterwave.com" and path == "/v3/transactions/verify_by_reference":
            ref = request.url.params["tx_ref"]
            body = self.sessions[ref]
            return httpx.Response(
                200,
                json={
                    "data": {
                        "status": self.status.get(ref, "pending"),
                        "tx_ref": ref,
                        "amount": body["amount"],
                        "currency": body["currency"],
                    }
                },
            )
        if host == "api.stripe.com" and path == "/v1/checkout/sessions":
            form = dict(httpx.QueryParams(request.content.decode()))
            sid = f"cs_test_{uuid.uuid4().hex}"
            self.sessions[sid] = form
            return httpx.Response(200, json={"id": sid, "url": f"https://checkout.stripe.com/c/pay/{sid}"})
        if host == "api.stripe.com" and path.startswith("/v1/checkout/sessions/"):
            sid = path.rsplit("/", 1)[1]
            form = self.sessions[sid]
            ref = form["client_reference_id"]
            return httpx.Response(
                200,
                json={
                    "id": sid,
                    "client_reference_id": ref,
                    "payment_status": self.status.get(ref, "unpaid"),
                    "status": "complete" if self.status.get(ref) == "paid" else "open",
                    "amount_total": int(form["line_items[0][price_data][unit_amount]"]),
                    "currency": form["line_items[0][price_data][currency]"],
                },
            )
        return httpx.Response(404, json={"message": "unknown"})


@pytest.fixture
def fake(monkeypatch):
    f = FakeGateways()
    monkeypatch.setattr(gateways, "transport", httpx.MockTransport(f.handler))
    return f


async def _provider(client, make_user, *, gateway=None, key=None, profile=True):
    user, headers = await make_user("provider")
    if profile:
        assert (await client.put("/api/v1/providers/me", json=PROFILE, headers=headers)).status_code == 200
    if gateway:
        resp = await client.put(f"/api/v1/providers/me/gateways/{gateway}", json={"secret_key": key}, headers=headers)
        assert resp.status_code == 200, resp.text
    me = (await client.get("/api/v1/providers/me", headers=headers)).json()
    return user, headers, me["id"]


async def _topup(client, customer, provider_id, **over):
    body = {"provider_id": provider_id, "amount": "5000", "currency": "NGN", "method": "gateway"} | over
    return await client.post("/api/v1/credits/topups", json=body, headers=customer)


async def _balance(client, headers) -> Decimal:
    rows = (await client.get("/api/v1/credits", headers=headers)).json()["balances"]
    return sum((Decimal(r["balance"]) for r in rows), Decimal(0))


async def test_providers_connect_their_own_gateway_keys_which_are_never_shown(client, db, make_user, fake):
    _, provider, pid = await _provider(client, make_user)
    url = "/api/v1/providers/me/gateways/paystack"
    assert (await client.put(url, json={"secret_key": "pk_live_" + "x" * 20}, headers=provider)).status_code == 422
    assert (await client.put(url, json={"secret_key": "sk_test_" + "w" * 32}, headers=provider)).status_code == 422
    ok = await client.put(url, json={"secret_key": PAYSTACK_KEY}, headers=provider)
    assert ok.status_code == 200 and ok.json() == ok.json() | {
        "gateway": "paystack",
        "key_hint": "pppp",
        "mode": "test",
    }
    listed = (await client.get("/api/v1/providers/me/gateways", headers=provider)).json()
    assert PAYSTACK_KEY not in json.dumps(listed)
    row = await db.find_one(ProviderGateway, {"provider_id": uuid.UUID(pid)})
    assert row.secret_encrypted.startswith("aesgcm:") and PAYSTACK_KEY not in row.secret_encrypted
    _, customer = await make_user("customer")
    assert (await client.put(url, json={"secret_key": PAYSTACK_KEY}, headers=customer)).status_code == 403


@pytest.mark.parametrize(
    ("gateway", "key", "success", "checkout_host"),
    [
        ("paystack", PAYSTACK_KEY, "success", "checkout.paystack.com"),
        ("flutterwave", FLW_KEY, "successful", "checkout.flutterwave.com"),
        ("stripe", STRIPE_KEY, "paid", "checkout.stripe.com"),
    ],
)
async def test_gateway_payments_are_verified_with_the_providers_gateway_and_credited_once(
    client, db, make_user, fake, gateway, key, success, checkout_host
):
    _, _, pid = await _provider(client, make_user, gateway=gateway, key=key)
    _, customer = await make_user("customer")
    started = await _topup(client, customer, pid, gateway=gateway)
    assert started.status_code == 201, started.text
    payment = started.json()
    assert payment["state"] == "PENDING" and httpx.URL(payment["checkout_url"]).host == checkout_host
    init = next(r for r in fake.requests if r.method == "POST" and "balance" not in r.url.path)
    assert init.headers["authorization"] == f"Bearer {key}"  # the provider's own account receives the money

    verify = f"/api/v1/credits/topups/{payment['id']}/verify"
    assert (await client.post(verify, headers=customer)).json()["state"] == "PENDING"  # not paid yet: no credit
    assert await _balance(client, customer) == 0
    fake.status[payment["reference"]] = success
    done = (await client.post(verify, headers=customer)).json()
    assert done["state"] == "VERIFIED" and await _balance(client, customer) == Decimal(5000)
    assert (await client.post(verify, headers=customer)).json()["state"] == "VERIFIED"
    assert await _balance(client, customer) == Decimal(5000)  # never credited twice
    assert await db.count(CreditEntry, {"kind": "payment"}) == 1


async def test_a_payment_for_a_different_amount_is_never_credited(client, db, make_user, fake):
    _, _, pid = await _provider(client, make_user, gateway="paystack", key=PAYSTACK_KEY)
    _, customer = await make_user("customer")
    payment = (await _topup(client, customer, pid, gateway="paystack")).json()
    fake.status[payment["reference"]] = "success"
    fake.amount_override[payment["reference"]] = 100  # 1.00 NGN paid instead of 5000
    out = (await client.post(f"/api/v1/credits/topups/{payment['id']}/verify", headers=customer)).json()
    assert out["state"] == "REVIEW" and await _balance(client, customer) == 0


async def test_failed_or_unreachable_gateways_credit_nothing(client, db, make_user, fake):
    _, _, pid = await _provider(client, make_user, gateway="paystack", key=PAYSTACK_KEY)
    _, customer = await make_user("customer")
    payment = (await _topup(client, customer, pid, gateway="paystack")).json()
    fake.down = True
    assert (await client.post(f"/api/v1/credits/topups/{payment['id']}/verify", headers=customer)).json()[
        "state"
    ] == "PENDING"
    fake.down = False
    fake.status[payment["reference"]] = "abandoned"
    out = (await client.post(f"/api/v1/credits/topups/{payment['id']}/verify", headers=customer)).json()
    assert out["state"] == "FAILED" and await _balance(client, customer) == 0
    # A provider without that gateway cannot be paid through it.
    _, _, other = await _provider(client, make_user)
    assert (await _topup(client, customer, other, gateway="stripe")).status_code == 409


async def test_pending_gateway_payments_are_verified_in_the_background(client, db, make_user, fake):
    _, _, pid = await _provider(client, make_user, gateway="paystack", key=PAYSTACK_KEY)
    _, customer = await make_user("customer")
    payment = (await _topup(client, customer, pid, gateway="paystack")).json()
    fake.status[payment["reference"]] = "success"
    assert await credit_service.run_pending(utcnow() + timedelta(minutes=1)) == 1
    assert await _balance(client, customer) == Decimal(5000)
    stale = (await _topup(client, customer, pid, gateway="paystack")).json()
    await credit_service.run_pending(utcnow() + timedelta(days=2))
    db.expire_all()
    assert (await db.get(CreditPayment, uuid.UUID(stale["id"]))).state == "FAILED"


async def test_manual_payments_are_credited_only_when_their_provider_confirms(client, db, make_user, fake):
    _, provider, pid = await _provider(client, make_user)
    _, other_provider, _ = await _provider(client, make_user)
    _, customer = await make_user("customer")
    assert (await _topup(client, customer, pid, method="manual")).status_code == 422  # needs a reference
    recorded = await _topup(client, customer, pid, method="manual", reference="TRF-0001", amount="2500")
    assert recorded.status_code == 201 and recorded.json()["state"] == "PENDING"
    assert (await _topup(client, customer, pid, method="manual", reference="TRF-0001")).status_code == 409
    assert await _balance(client, customer) == 0  # recording a transfer is not payment

    decision = f"/api/v1/credits/topups/{recorded.json()['id']}/decision"
    assert (await client.post(decision, json={"accept": True}, headers=customer)).status_code == 403
    assert (await client.post(decision, json={"accept": True}, headers=other_provider)).status_code == 404
    pending = (await client.get("/api/v1/credits", headers=provider)).json()["payments"]
    assert pending[0]["reference"] == "TRF-0001" and len(pending[0]["customer_ref"]) == 8
    ok = await client.post(decision, json={"accept": True}, headers=provider)
    assert ok.json()["state"] == "VERIFIED" and await _balance(client, customer) == Decimal(2500)
    assert (await client.post(decision, json={"accept": True}, headers=provider)).status_code == 409

    rejected = (await _topup(client, customer, pid, method="manual", reference="TRF-0002")).json()
    out = await client.post(
        f"/api/v1/credits/topups/{rejected['id']}/decision",
        json={"accept": False, "reason": "Not received"},
        headers=provider,
    )
    assert out.json()["state"] == "REJECTED" and await _balance(client, customer) == Decimal(2500)
    # Providers who never published how to be paid cannot take manual payments.
    _, _, silent = await _provider(client, make_user, profile=False)
    assert (await _topup(client, customer, silent, method="manual", reference="TRF-9")).status_code == 409


async def test_a_verified_top_up_resumes_a_deployment_paused_for_credit(
    client, db, make_user, enroll_node, ollama_model, fake
):
    provider_user, provider, pid = await _provider(client, make_user)
    node = await enroll_node(provider=provider)
    await client.put(
        f"/api/v1/nodes/{node['node_id']}/pricing",
        json={
            "currency": "NGN",
            "cpu_core_hour": "10",
            "ram_gb_hour": "20",
            "vram_gb_hour": "0",
            "input_tokens_per_million": "0",
            "output_tokens_per_million": "0",
        },
        headers=provider,
    )
    customer_user, customer = await make_user("customer")
    manual = (await _topup(client, customer, pid, method="manual", reference="TRF-A", amount="100")).json()
    await client.post(f"/api/v1/credits/topups/{manual['id']}/decision", json={"accept": True}, headers=provider)
    dep = (await client.post("/api/v1/deployments", json={"model_id": str(ollama_model.id)}, headers=customer)).json()
    assert dep["node_id"] == node["node_id"]
    await client.post(
        f"/api/v1/worker/deployments/{dep['id']}/status", json={"state": "READY"}, headers=node["headers"]
    )
    from app.services import placement_service

    row = await db.get(Deployment, uuid.UUID(dep["id"]))
    await placement_service.pause_for_credit(db, row)
    await db.commit()
    assert (await client.get(f"/api/v1/deployments/{dep['id']}", headers=customer)).json()[
        "error_code"
    ] == "CREDIT_EXHAUSTED"

    topup = (await _topup(client, customer, pid, method="manual", reference="TRF-B", amount="500")).json()
    await client.post(f"/api/v1/credits/topups/{topup['id']}/decision", json={"accept": True}, headers=provider)
    resumed = (await client.get(f"/api/v1/deployments/{dep['id']}", headers=customer)).json()
    assert resumed["status"] == "SCHEDULED" and resumed["node_id"] == node["node_id"]
    assert (await db.get(Provider, uuid.UUID(pid))) is not None
