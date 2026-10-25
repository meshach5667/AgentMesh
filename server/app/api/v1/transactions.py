"""The caller's ledger history: every entry that moved money into or out of their wallet, filterable and
exportable as CSV."""

import csv
import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.core.database import Session, get_db
from app.core.dependencies import get_current_user
from app.documents.transaction import Transaction
from app.documents.wallet import Wallet
from app.schemas.transaction import TransactionResponse, TransactionStatusEnum, TransactionTypeEnum

router = APIRouter()

EXPORT_LIMIT = 10_000


def ledger_filter(
    type: list[TransactionTypeEnum] | None,
    status: TransactionStatusEnum | None,
    since: datetime | None,
    until: datetime | None,
) -> dict[str, Any]:
    filter: dict[str, Any] = {}
    if type:
        filter["type"] = {"$in": [t.value for t in type]}
    if status:
        filter["status"] = status.value
    window = {k: v.replace(tzinfo=None) for k, v in (("$gte", since), ("$lt", until)) if v is not None}
    if window:
        filter["created_at"] = window
    return filter


async def _history(db: Session, user_id, filter: dict[str, Any], limit: int, offset: int) -> list[dict[str, Any]]:
    wallet = await db.find_one(Wallet, {"user_id": user_id})
    if not wallet:
        return []
    rows = await db.find(
        Transaction,
        {"$or": [{"from_wallet": wallet.id}, {"to_wallet": wallet.id}], **filter},
        sort=[("created_at", -1), ("_id", -1)],
        skip=offset,
        limit=limit,
    )
    return [
        TransactionResponse.model_validate(t).model_dump()
        | {"direction": "credit" if t.to_wallet == wallet.id else "debit"}
        for t in rows
    ]


@router.get("", response_model=list[TransactionResponse])
async def list_transactions(
    type: list[TransactionTypeEnum] | None = Query(None, description="Repeat to match several types"),
    status: TransactionStatusEnum | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=100_000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Newest first. Debits from the wallet (charges, payouts, card refunds, clawbacks) and credits to it (top-ups,
    earnings, refunds)."""
    return await _history(db, current_user.id, ledger_filter(type, status, since, until), limit, offset)


@router.get("/export.csv")
async def export_transactions(
    type: list[TransactionTypeEnum] | None = Query(None),
    status: TransactionStatusEnum | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """The same history as CSV (at most 10,000 rows), for bookkeeping."""
    rows = await _history(db, current_user.id, ledger_filter(type, status, since, until), EXPORT_LIMIT, 0)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["date_utc", "type", "direction", "amount", "status", "reference", "description", "id"])
    for r in rows:
        # A leading =, +, - or @ would be read as a formula by spreadsheet programs.
        description = r["description"] or ""
        if description[:1] in ("=", "+", "-", "@", "\t", "\r"):
            description = "'" + description
        writer.writerow(
            [r["created_at"].isoformat(), r["type"].value, r["direction"], r["amount"], r["status"].value,
             r["reference"] or "", description, r["id"]]
        )  # fmt: skip
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="agentmesh-transactions.csv"'},
    )
