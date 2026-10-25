"""Copy an AgentMesh PostgreSQL database into MongoDB (one-off, for moving an existing installation).

Every table is copied into the collection of the same name with the same ids and values, so API keys, node
credentials, deployment endpoints and ledger history keep working. Run it with the API stopped (no writes), then
start the MongoDB version of the API. It ends by running the ledger reconciliation report on the copy.

    pip install asyncpg   # only needed for this script
    POSTGRES_URL=postgresql://user:pass@host:5432/agentmesh \\
      MONGODB_URL=mongodb+srv://user:pass@cluster0.example.mongodb.net/ \\
      python scripts/migrate_postgres_to_mongo.py [--replace] [--dry-run]

The target collections must be empty; ``--replace`` empties them first (use it to redo a copy at cutover).
"""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import ReplaceOne  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.mongo import _encode, init_mongo, mongo_session  # noqa: E402
from app.documents import DOCUMENTS, Doc  # noqa: E402

BATCH = 500

Rows = Callable[[str], AsyncIterator[dict[str, Any]]]


def to_document(doc_cls: type[Doc], row: dict[str, Any]) -> tuple[Doc, set[str]]:
    """Build a document from a table row. Returns it and the columns it has no field for (left out)."""
    fields = doc_cls.model_fields
    values = {}
    for column, value in row.items():
        if isinstance(value, datetime) and value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)  # documents hold naive UTC
        values[column] = value
    unknown = set(values) - set(fields)
    return doc_cls.model_validate({k: v for k, v in values.items() if k in fields}), unknown


async def copy_table(doc_cls: type[Doc], rows: Rows, *, dry_run: bool) -> tuple[int, set[str]]:
    collection = doc_cls.get_pymongo_collection()
    copied, unknown, batch = 0, set(), []

    async def flush() -> None:
        if batch and not dry_run:
            await collection.bulk_write(batch, ordered=False)
        batch.clear()

    async for row in rows(doc_cls.get_settings().name):
        doc, extra = to_document(doc_cls, row)
        unknown |= extra
        batch.append(ReplaceOne({"_id": doc.id}, _encode(doc), upsert=True))
        copied += 1
        if len(batch) >= BATCH:
            await flush()
    await flush()
    return copied, unknown


async def migrate(rows: Rows, tables: set[str], *, replace: bool, dry_run: bool, log=print) -> dict[str, int]:
    """Copy every table that exists in PostgreSQL. MongoDB must be initialised (init_mongo)."""
    if not replace:
        busy = [d.get_settings().name for d in DOCUMENTS if await d.get_pymongo_collection().estimated_document_count()]
        if busy:
            raise SystemExit(f"Target collections are not empty: {', '.join(sorted(busy))}. Use --replace.")
    counts: dict[str, int] = {}
    for doc_cls in DOCUMENTS:
        name = doc_cls.get_settings().name
        if name not in tables:
            log(f"{name}: no such table, skipped")
            continue
        if replace and not dry_run:
            await doc_cls.get_pymongo_collection().delete_many({})
        counts[name], unknown = await copy_table(doc_cls, rows, dry_run=dry_run)
        note = f" (columns not copied: {', '.join(sorted(unknown))})" if unknown else ""
        log(f"{name}: {counts[name]} rows{note}")
    return counts


async def _reconcile(log=print) -> bool:
    from app.services import reconciliation_service

    async with mongo_session() as db:
        report = await reconciliation_service.report(db)
    log(f"Reconciliation: {'ok' if report['ok'] else 'ISSUES FOUND'} {report['checked']}")
    for issue in report["issues"][:20]:
        log(f"  {issue}")
    return bool(report["ok"])


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--replace", action="store_true", help="Empty the target collections first")
    ap.add_argument("--dry-run", action="store_true", help="Read and convert everything, write nothing")
    args = ap.parse_args()
    try:
        import asyncpg
    except ImportError:
        raise SystemExit("This script needs asyncpg: pip install asyncpg") from None
    url = os.environ.get("POSTGRES_URL")
    if not url:
        raise SystemExit("Set POSTGRES_URL to the source database")
    conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    for codec in ("json", "jsonb"):
        await conn.set_type_codec(codec, encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    tables = {
        r["table_name"]
        for r in await conn.fetch("select table_name from information_schema.tables where table_schema = 'public'")
    }

    async def rows(table: str) -> AsyncIterator[dict[str, Any]]:
        async for record in conn.cursor(f'select * from "{table}"'):
            yield dict(record)

    await init_mongo()
    print(f"Copying PostgreSQL into MongoDB database {settings.MONGODB_DB}{' (dry run)' if args.dry_run else ''}")
    async with conn.transaction(readonly=True, isolation="repeatable_read"):  # one consistent snapshot
        await migrate(rows, tables, replace=args.replace, dry_run=args.dry_run)
    await conn.close()
    if not args.dry_run and not await _reconcile():
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
