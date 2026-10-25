"""Read-only aggregates for dashboards: usage summaries (customer, provider, operator), the operator overview,
and the public network figures shown on the landing page.

Everything here is computed from stored records. Token counts are summed only where the runtime reported them;
requests without counts are reported separately and never estimated.
"""

import uuid
from datetime import timedelta
from typing import Any

from app.core.config import settings
from app.core.database import Session
from app.core.timeutil import utcnow
from app.documents.deployment import Deployment, DeploymentStatus
from app.documents.model import Model, ModelArtifact
from app.documents.node import Node, NodeStatus
from app.documents.transaction import Transaction
from app.documents.usage import UsageRecord
from app.documents.user import Customer, Provider, User

# Nodes the scheduler may consider (see scheduler_service); used for "online" counts.
ONLINE_NODE_STATUSES = [NodeStatus.ONLINE.value, NodeStatus.AVAILABLE.value, NodeStatus.BUSY.value]

USAGE_TOTALS: dict[str, Any] = {
    "requests": {"$sum": 1},
    "succeeded": {"$sum": {"$cond": [{"$eq": ["$outcome", "success"]}, 1, 0]}},
    "input_tokens": {"$sum": "$input_tokens"},
    "output_tokens": {"$sum": "$output_tokens"},
    "unreported": {"$sum": {"$cond": [{"$eq": [{"$ifNull": ["$output_tokens", None]}, None]}, 1, 0]}},
}


def _usage_row(row: dict[str, Any] | None) -> dict[str, int]:
    row = row or {}
    requests = int(row.get("requests") or 0)
    succeeded = int(row.get("succeeded") or 0)
    return {
        "requests": requests,
        "succeeded": succeeded,
        "failed": requests - succeeded,
        "input_tokens": int(row.get("input_tokens") or 0),
        "output_tokens": int(row.get("output_tokens") or 0),
        "requests_without_token_counts": int(row.get("unreported") or 0),
    }


async def _usage(db: Session, match: dict[str, Any], key: Any = None, **stages: Any) -> list[dict[str, Any]]:
    pipeline: list[dict[str, Any]] = [{"$match": match}, {"$group": {"_id": key, **USAGE_TOTALS}}]
    pipeline += [{f"${name}": value} for name, value in stages.items()]
    return await db.aggregate(UsageRecord, pipeline)


async def customer_deployment_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    customer = await db.find_one(Customer, {"user_id": user_id})
    return await db.distinct(Deployment, "_id", {"customer_id": customer.id}) if customer else []


async def provider_node_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    provider = await db.find_one(Provider, {"user_id": user_id})
    return await db.distinct(Node, "_id", {"owner_id": provider.id}) if provider else []


async def usage_summary(db: Session, user: User, days: int, scope: str) -> dict[str, Any]:
    """Inference usage over the last ``days`` days for the caller's ``scope``: "customer" (their deployments),
    "provider" (requests served by their nodes) or "network" (everything; staff only, checked by the caller)."""
    since = utcnow() - timedelta(days=days)
    match: dict[str, Any] = {"kind": "inference", "created_at": {"$gte": since}}
    if scope == "customer":
        match["deployment_id"] = {"$in": await customer_deployment_ids(db, user.id)}
    elif scope == "provider":
        match["node_id"] = {"$in": await provider_node_ids(db, user.id)}

    totals = await _usage(db, match)
    per_day = await _usage(db, match, {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}, sort={"_id": 1})
    per_dep = await _usage(db, match, "$deployment_id", sort={"requests": -1, "_id": 1}, limit=50)
    return {
        "scope": scope,
        "days": days,
        "since": since,
        "totals": _usage_row(totals[0] if totals else None),
        "by_day": [{"date": r["_id"], **_usage_row(r)} for r in per_day],
        "by_deployment": [{"deployment_id": r["_id"], **_usage_row(r)} for r in per_dep if r["_id"]],
        "token_source": "runtime_reported",
    }


async def _count_by(db: Session, doc: type, field: str, match: dict[str, Any] | None = None) -> dict[str, int]:
    rows = await db.aggregate(doc, [{"$match": match or {}}, {"$group": {"_id": f"${field}", "n": {"$sum": 1}}}])
    return {str(r["_id"]): int(r["n"]) for r in rows if r["_id"] is not None}


async def _deployable_models(db: Session) -> int:
    has_artifact = await db.distinct(ModelArtifact, "model_id", {"is_enabled": True})
    return await db.count(Model, {"is_approved": True, "_id": {"$in": has_artifact}})


async def public_stats(db: Session) -> dict[str, Any]:
    """Counts only: no node names, owners, locations, or hardware details."""
    online = await db.find(Node, {"status": {"$in": ONLINE_NODE_STATUSES}, "accepting_workloads": True})
    runtimes = sorted(
        {
            str(r["name"])
            for node in online
            for r in (node.runtimes or [])
            if isinstance(r, dict) and r.get("available") and r.get("name")
        }
    )
    return {
        "nodes_online": len(online),
        "gpu_nodes_online": sum(1 for n in online if (n.allocated_vram_mb or 0) > 0),
        "runtimes_online": runtimes,
        "models_deployable": await _deployable_models(db),
        "deployments_ready": await db.count(Deployment, {"status": DeploymentStatus.READY.value}),
        "features": {
            "test_credits": settings.test_credits_enabled,
            "payments": False,
            "provider_payouts": False,
            "confidential_computing": False,
        },
        "generated_at": utcnow(),
    }


async def operator_overview(db: Session) -> dict[str, Any]:
    since = utcnow() - timedelta(hours=24)
    usage = await _usage(db, {"kind": "inference", "created_at": {"$gte": since}})
    ledger = await db.aggregate(
        Transaction,
        [
            {
                "$group": {
                    "_id": {"type": "$type", "status": "$status"},
                    "n": {"$sum": 1},
                    "amount": {"$sum": "$amount"},
                }
            },
            {"$sort": {"_id.type": 1, "_id.status": 1}},
        ],
    )
    stale_cutoff = utcnow() - timedelta(seconds=settings.HEARTBEAT_TIMEOUT_SECONDS)
    return {
        "nodes_by_status": await _count_by(db, Node, "status"),
        "nodes_paused": await db.count(Node, {"accepting_workloads": False}),
        "nodes_heartbeat_overdue": await db.count(
            Node, {"status": {"$in": ONLINE_NODE_STATUSES}, "last_heartbeat": {"$lt": stale_cutoff}}
        ),
        "deployments_by_status": await _count_by(db, Deployment, "status", {"deleted_at": None}),
        "deployments_by_runtime": await _count_by(db, Deployment, "runtime", {"status": DeploymentStatus.READY.value}),
        "models": {
            "total": await db.count(Model),
            "approved": await db.count(Model, {"is_approved": True}),
            "deployable": await _deployable_models(db),
        },
        "users_by_role": await _count_by(db, User, "role"),
        "usage_24h": _usage_row(usage[0] if usage else None),
        "ledger": [
            {
                "type": str(r["_id"].get("type")),
                "status": str(r["_id"].get("status")),
                "count": int(r["n"]),
                "amount": str(r["amount"].to_decimal() if hasattr(r["amount"], "to_decimal") else r["amount"]),
            }
            for r in ledger
        ],
        "generated_at": utcnow(),
    }


async def emails_by_profile(db: Session, profile: type[Customer] | type[Provider], ids: set) -> dict[Any, str]:
    """Account email for each Customer or Provider id."""
    profiles = await db.find(profile, {"_id": {"$in": [i for i in ids if i is not None]}})
    users = {u.id: u.email for u in await db.find(User, {"_id": {"$in": [p.user_id for p in profiles]}})}
    return {p.id: users[p.user_id] for p in profiles if p.user_id in users}


async def list_nodes_with_owner(db: Session, status: str | None, limit: int) -> list[tuple[Node, str | None]]:
    nodes = await db.find(Node, {"status": status} if status else {}, sort=[("created_at", -1)], limit=limit)
    emails = await emails_by_profile(db, Provider, {n.owner_id for n in nodes})
    return [(n, emails.get(n.owner_id)) for n in nodes]


async def list_deployments_with_owner(
    db: Session, status: str | None, node_id: uuid.UUID | None, limit: int
) -> list[tuple[Deployment, str | None]]:
    match: dict[str, Any] = {}
    if status:
        match["status"] = status
    if node_id:
        match["node_id"] = node_id
    deps = await db.find(Deployment, match, sort=[("created_at", -1)], limit=limit)
    emails = await emails_by_profile(db, Customer, {d.customer_id for d in deps})
    return [(d, emails.get(d.customer_id)) for d in deps]
