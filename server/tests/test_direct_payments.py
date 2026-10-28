"""Direct provider payments: providers publish how customers pay them; AgentMesh shows it and processes nothing.
No payment gateway, no commission, no subscription, and no payment state that could be "verified" by a click."""

from pathlib import Path

import pytest

from app.main import app

PROFILE = {
    "display_name": "Lagos GPU Co",
    "description": "RTX 4090 machines in Lagos.",
    "payment": {
        "methods": ["bank_transfer", "payment_link"],
        "accepted_currencies": ["NGN", "USD"],
        "instructions": "Transfer to our business account and use your deployment id as the reference.",
        "links": [{"label": "Pay online", "url": "https://pay.example.com/lagos-gpu"}],
        "terms": "Invoiced weekly; due within 7 days.",
        "minimum_amount": "5000",
        "minimum_currency": "NGN",
        "minimum_note": "Minimum weekly invoice",
    },
}


async def test_a_provider_publishes_a_profile_and_payment_arrangement(client, make_user):
    _, provider = await make_user("provider")
    resp = await client.put("/api/v1/providers/me", json=PROFILE, headers=provider)
    assert resp.status_code == 200, resp.text
    me = (await client.get("/api/v1/providers/me", headers=provider)).json()
    assert me["display_name"] == "Lagos GPU Co" and me["payment"]["methods"] == ["bank_transfer", "payment_link"]
    assert me["payment"]["links"][0]["url"] == "https://pay.example.com/lagos-gpu"


@pytest.mark.parametrize(
    "url",
    [
        "http://pay.example.com/x",  # not https
        "javascript:alert(1)",
        "https://user:pass@pay.example.com/",  # credentials in the URL
        "https://localhost/pay",
        "https://127.0.0.1/pay",
        "https://10.0.0.5/pay",
        "https://pay.internal/x",
        "https://pay.example.com:8443/x",
        "https://pay.example.com/a b",
        "//pay.example.com/x",
    ],
)
async def test_unsafe_payment_links_are_rejected(client, make_user, url):
    _, provider = await make_user("provider")
    body = PROFILE | {"payment": PROFILE["payment"] | {"links": [{"label": "Pay", "url": url}]}}
    assert (await client.put("/api/v1/providers/me", json=body, headers=provider)).status_code == 422


@pytest.mark.parametrize(
    "instructions",
    [
        "Send us your card PIN to confirm.",
        "Reply with the OTP you receive.",
        "We need your banking password.",
        "Give us the CVV on the back.",
        "Pay with card 4111 1111 1111 1111.",
    ],
)
async def test_instructions_cannot_ask_for_secrets_or_carry_card_numbers(client, make_user, instructions):
    _, provider = await make_user("provider")
    body = PROFILE | {"payment": PROFILE["payment"] | {"instructions": instructions}}
    assert (await client.put("/api/v1/providers/me", json=body, headers=provider)).status_code == 422


async def test_only_the_provider_edits_its_own_profile(client, make_user):
    _, customer = await make_user("customer")
    _, operator = await make_user("operator")
    for headers in (customer, operator):
        assert (await client.put("/api/v1/providers/me", json=PROFILE, headers=headers)).status_code == 403
    assert (await client.put("/api/v1/providers/me", json=PROFILE)).status_code == 401
    # There is no route to edit someone else's profile.
    paths = {r.path for r in app.routes if hasattr(r, "methods") and "PUT" in r.methods}
    assert "/api/v1/providers/{provider_id}" not in paths


async def test_customers_see_offers_prices_and_how_to_pay_before_choosing(
    client, db, make_user, enroll_node, ollama_model
):
    provider_user, provider = await make_user("provider")
    await client.put("/api/v1/providers/me", json=PROFILE, headers=provider)
    node = await enroll_node(provider=provider)
    await client.put(
        f"/api/v1/nodes/{node['node_id']}/pricing",
        json={
            "currency": "NGN",
            "cpu_core_hour": "15",
            "ram_gb_hour": "5",
            "vram_gb_hour": "0",
            "input_tokens_per_million": "0",
            "output_tokens_per_million": "0",
        },
        headers=provider,
    )
    _, customer = await make_user("customer")
    offers = (await client.get("/api/v1/providers", headers=customer)).json()
    (offer,) = offers
    assert offer["display_name"] == "Lagos GPU Co" and offer["machines_available"] == 1
    assert offer["prices"][0]["currency"] == "NGN" and offer["payment_methods"] == ["bank_transfer", "payment_link"]
    assert node["node_id"] not in str(offers)  # aggregates only
    detail = (await client.get(f"/api/v1/providers/{offer['id']}", headers=customer)).json()
    assert detail["payment"]["instructions"].startswith("Transfer to our business account")
    assert (await client.get("/api/v1/providers")).status_code == 401  # signed-in users only

    # Choosing this provider restricts placement to its machines, and the deployment shows how to pay it.
    dep = (
        await client.post(
            "/api/v1/deployments",
            json={"model_id": str(ollama_model.id), "provider_id": offer["id"]},
            headers=customer,
        )
    ).json()
    assert dep["node_id"] == node["node_id"] and dep["provider_id"] == offer["id"]
    pricing = (await client.get(f"/api/v1/deployments/{dep['id']}/pricing", headers=customer)).json()
    assert pricing["provider"]["payment"]["links"][0]["label"] == "Pay online"


async def test_a_chosen_provider_without_capacity_is_not_silently_replaced(
    client, make_user, enroll_node, ollama_model
):
    _, chosen = await make_user("provider")
    me = (await client.get("/api/v1/providers/me", headers=chosen)).json()
    await enroll_node()  # another provider's machine has room
    _, customer = await make_user("customer")
    resp = await client.post(
        "/api/v1/deployments", json={"model_id": str(ollama_model.id), "provider_id": me["id"]}, headers=customer
    )
    assert resp.status_code == 503 and resp.json()["detail"]["reasons"] == {"other_provider": 1}


async def test_providers_participate_free_and_no_payment_state_exists(client, make_user, enroll_node):
    """Enrolling, pricing and publishing need no payment to AgentMesh; nothing records payments as completed."""
    _, provider = await make_user("provider")
    node = await enroll_node(provider=provider)
    assert (await client.put("/api/v1/providers/me", json=PROFILE, headers=provider)).status_code == 200
    shown = (await client.get(f"/api/v1/nodes/{node['node_id']}", headers=provider)).json()
    assert shown["schedulable"] is True
    paths = " ".join(sorted({getattr(r, "path", "") for r in app.routes}))
    for word in ("paystack", "wallet", "payout", "topup", "commission", "subscription", "checkout", "refund"):
        assert word not in paths.lower(), word


def test_no_payment_gateway_code_or_dependency_remains():
    root = Path(__file__).resolve().parents[1]
    sources = [p for p in (root / "app").rglob("*.py")]
    assert not [p for p in sources if "paystack" in p.read_text().lower()]
    for name in ("requirements.txt", "requirements-lock.txt"):
        path = root / name
        if path.exists():
            assert "paystack" not in path.read_text().lower()
