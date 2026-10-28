"""Provider profiles, payment arrangements and the compute offers customers browse.

Offers are aggregates per provider (how many machines can take work, GPUs, runtimes, lowest prices per currency);
no machine is named and no address is exposed. Payment arrangements are shown to signed-in customers only.
"""

import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from app.core.database import Session
from app.core.timeutil import utcnow
from app.documents.node import Node
from app.documents.user import Provider, User
from app.schemas.provider import PaymentProfile
from app.services import audit_service
from app.services.node_pricing_service import rates_at
from app.services.scheduler_service import schedulable


def display_name(provider: Provider) -> str:
    return provider.display_name or f"Provider {str(provider.id)[:8]}"


def payment_of(provider: Provider) -> PaymentProfile | None:
    if not provider.payment_profile:
        return None
    try:
        return PaymentProfile.model_validate(provider.payment_profile)
    except ValueError:
        return None  # saved before a stricter rule: not shown until the provider saves it again


def has_arrangement(p: PaymentProfile | None) -> bool:
    return p is not None and bool(p.methods or p.instructions or p.links)


def card(provider: Provider) -> dict:
    """What a customer sees about who runs their machine and how to pay them."""
    payment = payment_of(provider)
    return {
        "id": str(provider.id),
        "display_name": display_name(provider),
        "description": provider.description,
        "payment": payment.model_dump(mode="json") if payment else None,
    }


async def update_profile(db: Session, provider: Provider, data: dict, actor: User) -> Provider:
    provider.display_name = data["display_name"]
    provider.description = data.get("description")
    provider.payment_profile = data.get("payment") or None
    db.add(provider)
    audit_service.record(
        db,
        actor_id=actor.id,
        action="provider.profile_updated",
        resource_type="provider",
        resource_id=provider.id,
        details={
            "methods": (data.get("payment") or {}).get("methods", []),
            "links": len((data.get("payment") or {}).get("links", [])),
        },
    )
    await db.commit()
    await db.refresh(provider)
    return provider


async def offers(db: Session, provider_id: uuid.UUID | None = None) -> list[dict]:
    """Providers with at least one machine that can take work now, cheapest-friendly summary first."""
    now = utcnow()
    query: dict = {"mode": {"$ne": None}}
    if provider_id is not None:
        query["owner_id"] = provider_id
    nodes = [n for n in await db.find(Node, query) if schedulable(n, now)]
    rates = await rates_at(db, [n.id for n in nodes], now)
    by_provider: dict[uuid.UUID, list[Node]] = {}
    for n in nodes:
        by_provider.setdefault(n.owner_id, []).append(n)
    providers = {p.id: p for p in await db.find(Provider, {"_id": {"$in": list(by_provider)}})}
    connected = await _gateways_by_provider(db, list(by_provider))
    out: list[dict[str, Any]] = []
    for pid, machines in by_provider.items():
        provider = providers.get(pid)
        if provider is None:
            continue
        prices: dict[str, dict] = {}
        free = 0
        for n in machines:
            r = rates[n.id]
            if r is None or r.is_free():
                free += 1
                continue
            p = prices.setdefault(
                r.currency,
                {
                    "currency": r.currency,
                    "cpu_core_hour": r.cpu_core_hour,
                    "ram_gb_hour": r.ram_gb_hour,
                    "vram_gb_hour": r.vram_gb_hour,
                    "input_tokens_per_million": r.input_tokens_per_million,
                    "output_tokens_per_million": r.output_tokens_per_million,
                },
            )
            for f in (
                "cpu_core_hour",
                "ram_gb_hour",
                "vram_gb_hour",
                "input_tokens_per_million",
                "output_tokens_per_million",
            ):
                p[f] = min(p[f], getattr(r, f))
        payment = payment_of(provider)
        out.append(
            {
                "id": str(pid),
                "display_name": display_name(provider),
                "description": provider.description,
                "machines_available": len(machines),
                "gpu_machines": sum(1 for n in machines if (n.allocated_vram_mb or 0) > 0),
                "runtimes": sorted(
                    {
                        str(r["name"])
                        for n in machines
                        for r in (n.runtimes or [])
                        if isinstance(r, dict) and r.get("available")
                    }
                ),
                "free_machines": free,
                "prices": [
                    {k: (str(v) if isinstance(v, Decimal) else v) for k, v in p.items()} for p in prices.values()
                ],
                "payment_methods": list(payment.methods) if payment else [],
                "accepts_payment_arrangement": has_arrangement(payment),
                "gateways": connected.get(pid, []),
                "payment": payment.model_dump(mode="json") if payment else None,
            }
        )
    out.sort(key=lambda o: (-o["machines_available"], o["display_name"].lower(), o["id"]))
    return out


async def get_provider(db: Session, provider_id: str) -> Provider:
    try:
        pid = uuid.UUID(provider_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Provider not found") from None
    provider = await db.get(Provider, pid)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


async def detail(db: Session, provider: Provider) -> dict:
    found = await offers(db, provider.id)
    if found:
        return found[0]
    payment = payment_of(provider)
    return {
        "id": str(provider.id),
        "display_name": display_name(provider),
        "description": provider.description,
        "machines_available": 0,
        "gpu_machines": 0,
        "runtimes": [],
        "free_machines": 0,
        "prices": [],
        "payment_methods": list(payment.methods) if payment else [],
        "accepts_payment_arrangement": has_arrangement(payment),
        "gateways": (await _gateways_by_provider(db, [provider.id])).get(provider.id, []),
        "payment": payment.model_dump(mode="json") if payment else None,
    }


async def _gateways_by_provider(db: Session, provider_ids: list) -> dict[uuid.UUID, list[str]]:
    from app.documents.credit import ProviderGateway

    out: dict[uuid.UUID, list[str]] = {}
    for g in await db.find(ProviderGateway, {"provider_id": {"$in": provider_ids}}, sort=[("gateway", 1)]):
        out.setdefault(g.provider_id, []).append(g.gateway)
    return out
