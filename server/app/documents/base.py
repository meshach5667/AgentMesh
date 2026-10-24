"""Shared base for MongoDB documents.

Ids stay UUIDs (stored as standard BSON UUIDs in ``_id``) so ids already handed out by the PostgreSQL schema keep
their meaning after migration. Money is ``Money`` (BSON Decimal128): exact, never a float.
"""

import uuid
from decimal import Decimal
from typing import Any

from beanie import DecimalAnnotation, Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

Money = DecimalAnnotation
ZERO = Decimal("0")


class Doc(Document):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)  # type: ignore[assignment]

    class Settings:
        # save_changes() then writes only the changed fields ($set), so it never overwrites a concurrent atomic
        # update of another field (e.g. a node's reserved capacity).
        use_state_management = True
        keep_nulls = True


def unique(*fields: str, name: str, nullable: tuple[str, ...] = (), where: dict[str, Any] | None = None) -> IndexModel:
    """A unique index. Like SQL, documents where a ``nullable`` (string) field is null never conflict; Mongo would
    otherwise treat null as a value and allow only one. ``where`` makes it partial (e.g. one ACTIVE row)."""
    partial = {f: {"$type": "string"} for f in nullable} | (where or {})
    kwargs: dict[str, Any] = {"unique": True, "name": name}
    if partial:
        kwargs["partialFilterExpression"] = partial
    return IndexModel([(f, ASCENDING) for f in fields], **kwargs)


def index(*fields: str) -> IndexModel:
    return IndexModel([(f, ASCENDING) for f in fields])
