"""MongoDB connection and the unit-of-work ``Session`` the services use.

A Session works like the SQLAlchemy session it replaces: documents loaded through it or added to it are tracked
(one in-memory instance per id), changed in memory, and written together by ``commit()`` in one transaction, so a
ledger posting and the balance it changes are saved together or not at all. Operations that must take effect
immediately (``update_one``: atomic conditional updates such as reserving node capacity; ``flush``) run in that
same transaction, which then stays open until ``commit()`` or ``rollback()``. Like SQLAlchemy's autoflush, pending
changes are flushed before a query or an atomic update, so they see everything added or changed so far.
"""

import asyncio
import random
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from beanie import SortDirection, init_beanie
from beanie.odm.utils.dump import get_dict
from pymongo import AsyncMongoClient
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.errors import PyMongoError

from app.core.config import settings
from app.core.timeutil import utcnow
from app.documents import DOCUMENTS, Doc

D = TypeVar("D", bound=Doc)

# A commit that only writes tracked changes is replayed after a transient write conflict (another transaction
# touched the same document); MongoDB aborts such transactions instead of waiting the way PostgreSQL does.
COMMIT_ATTEMPTS = 3

_client: AsyncMongoClient | None = None


def make_client(url: str) -> AsyncMongoClient:
    return AsyncMongoClient(url, uuidRepresentation="standard", tz_aware=False)


async def init_mongo(url: str | None = None, db_name: str | None = None) -> AsyncMongoClient:
    """Connect, register every document, and create missing indexes."""
    global _client
    client = make_client(url or settings.MONGODB_URL)
    database = client[db_name or settings.MONGODB_DB]
    # Create every collection up front instead of implicitly on first insert (which may be inside a transaction).
    existing = set(await database.list_collection_names())
    for name in {doc.Settings.name for doc in DOCUMENTS} - existing:  # type: ignore[attr-defined]
        await database.create_collection(name)
    await init_beanie(database=database, document_models=DOCUMENTS)
    _client = client
    return client


async def close_mongo() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def get_client() -> AsyncMongoClient:
    if _client is None:
        raise RuntimeError("MongoDB is not initialised (init_mongo was not called)")
    return _client


def _encode(doc: Doc) -> dict[str, Any]:
    encoded: dict[str, Any] = get_dict(doc, to_db=True, keep_nulls=True)
    return encoded


class Session:
    def __init__(self, client: AsyncMongoClient | None = None):
        self._given_client = client  # resolved on first use, so creating a Session never needs a connection
        self._identity: dict[tuple[type[Doc], Any], Doc] = {}
        self._new: list[Doc] = []
        self._deleted: list[Doc] = []
        self._txn: AsyncClientSession | None = None
        # Writes already sent inside the open transaction; a commit that fails after them cannot be replayed.
        self._sent = False

    @property
    def _client(self) -> AsyncMongoClient:
        return self._given_client or get_client()

    # --- Tracking ----------------------------------------------------------------------------------------------

    def _track(self, doc: D) -> D:
        key = (type(doc), doc.id)
        existing = self._identity.get(key)
        if existing is not None:
            return existing  # type: ignore[return-value]
        self._identity[key] = doc
        return doc

    def add(self, doc: Doc) -> None:
        key = (type(doc), doc.id)
        if self._identity.get(key) is doc:
            return
        self._identity[key] = doc
        self._new.append(doc)

    def add_all(self, docs: Sequence[Doc]) -> None:
        for doc in docs:
            self.add(doc)

    async def delete(self, doc: Doc) -> None:
        if doc in self._new:
            self._new.remove(doc)
        else:
            self._deleted.append(doc)
        self._identity.pop((type(doc), doc.id), None)

    # --- Reads -------------------------------------------------------------------------------------------------

    async def get(self, model: type[D], id: Any) -> D | None:
        if id is None:
            return None
        cached = self._identity.get((model, id))
        if cached is not None:
            return cached  # type: ignore[return-value]
        doc = await model.get(id, session=self._txn)
        return self._track(doc) if doc is not None else None

    def _dirty(self) -> bool:
        if self._new or self._deleted:
            return True
        new = {id(d) for d in self._new}
        return any(id(doc) not in new and doc.get_changes() for doc in self._identity.values())

    async def _autoflush(self) -> None:
        if self._dirty():
            await self.flush()

    async def find(
        self,
        model: type[D],
        filter: Mapping[str, Any] | None = None,
        *,
        sort: Sequence[tuple[str, int]] | None = None,
        skip: int | None = None,
        limit: int | None = None,
    ) -> list[D]:
        await self._autoflush()
        query = model.find(dict(filter or {}), session=self._txn)
        if sort:
            query = query.sort([(field, SortDirection(direction)) for field, direction in sort])
        if skip:
            query = query.skip(skip)
        if limit:
            query = query.limit(limit)
        return [self._track(doc) for doc in await query.to_list()]

    async def find_one(
        self, model: type[D], filter: Mapping[str, Any] | None = None, *, sort: Sequence[tuple[str, int]] | None = None
    ) -> D | None:
        found = await self.find(model, filter, sort=sort, limit=1)
        return found[0] if found else None

    async def count(self, model: type[D], filter: Mapping[str, Any] | None = None) -> int:
        await self._autoflush()
        return await model.get_pymongo_collection().count_documents(dict(filter or {}), session=self._txn)

    async def distinct(self, model: type[Doc], field: str, filter: Mapping[str, Any] | None = None) -> list[Any]:
        await self._autoflush()
        return await model.get_pymongo_collection().distinct(field, dict(filter or {}), session=self._txn)

    async def aggregate(self, model: type[Doc], pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        await self._autoflush()
        cursor = await model.get_pymongo_collection().aggregate(pipeline, session=self._txn)
        return await cursor.to_list()

    def expire_all(self) -> None:
        """Forget loaded documents (so the next read fetches them again), keeping ones added but not yet saved."""
        new = {id(d) for d in self._new}
        self._identity = {k: d for k, d in self._identity.items() if id(d) in new}

    async def ping(self) -> None:
        await self._client.admin.command("ping")

    async def refresh(self, doc: Doc) -> None:
        """Reload a document's fields from the database (e.g. after an atomic ``update_one``). Unsaved changes made
        to it in memory are kept on top and still written by the next commit, as SQLAlchemy's autoflush would."""
        raw = await type(doc).get_pymongo_collection().find_one({"_id": doc.id}, session=self._txn)
        if raw is None:
            raise LookupError(f"{type(doc).__name__} {doc.id} no longer exists")
        local = {name: getattr(doc, name) for name in {key.split(".")[0] for key in doc.get_changes()}}
        fresh = type(doc).model_validate(raw)
        for name in type(doc).model_fields:
            setattr(doc, name, getattr(fresh, name))
        doc._save_state()
        for name, value in local.items():
            setattr(doc, name, value)

    # --- Immediate writes (inside the open transaction) ----------------------------------------------------------

    async def _begin(self) -> AsyncClientSession:
        if self._txn is None:
            self._txn = self._client.start_session()
            await self._txn.start_transaction()
        return self._txn

    async def update_one(self, model: type[Doc], filter: Mapping[str, Any], update: Mapping[str, Any]) -> bool:
        """Atomic conditional update; True if a document matched. Use it where SQL used ``UPDATE ... WHERE``."""
        await self._autoflush()
        txn = await self._begin()
        self._sent = True
        result = await model.get_pymongo_collection().update_one(dict(filter), dict(update), session=txn)
        return result.matched_count > 0

    async def update_many(self, model: type[Doc], filter: Mapping[str, Any], update: Mapping[str, Any]) -> int:
        """Atomic update of every matching document; returns how many matched."""
        await self._autoflush()
        txn = await self._begin()
        self._sent = True
        result = await model.get_pymongo_collection().update_many(dict(filter), dict(update), session=txn)
        return result.matched_count

    async def delete_many(self, model: type[Doc], filter: Mapping[str, Any]) -> int:
        await self._autoflush()
        txn = await self._begin()
        self._sent = True
        result = await model.get_pymongo_collection().delete_many(dict(filter), session=txn)
        return result.deleted_count

    async def flush(self) -> None:
        """Send pending writes now (inside the transaction), e.g. to surface a duplicate key before going on."""
        txn = await self._begin()
        self._sent = True
        written = await self._write(txn)
        for doc in written:
            doc._save_state()
        self._new.clear()
        self._deleted.clear()

    # --- Commit / rollback -------------------------------------------------------------------------------------

    def _pending_updates(self) -> list[tuple[Doc, dict[str, Any]]]:
        updates = []
        new = {id(d) for d in self._new}
        for doc in self._identity.values():
            if id(doc) in new:
                continue
            changes = doc.get_changes()
            if changes:
                if "updated_at" in type(doc).model_fields and "updated_at" not in changes:
                    doc.updated_at = utcnow()  # type: ignore[attr-defined]
                    changes = doc.get_changes()
                updates.append((doc, changes))
        return updates

    async def _write(self, txn: AsyncClientSession) -> list[Doc]:
        updates = self._pending_updates()
        for doc in self._new:
            await type(doc).get_pymongo_collection().insert_one(_encode(doc), session=txn)
        for doc, changes in updates:
            await type(doc).get_pymongo_collection().update_one({"_id": doc.id}, {"$set": changes}, session=txn)
        for doc in self._deleted:
            await type(doc).get_pymongo_collection().delete_one({"_id": doc.id}, session=txn)
        return [*self._new, *(doc for doc, _ in updates)]

    async def commit(self) -> None:
        for attempt in range(1, COMMIT_ATTEMPTS + 1):
            try:
                txn = await self._begin()
                written = await self._write(txn)
                await txn.commit_transaction()
            except PyMongoError as exc:
                replayable = not self._sent and exc.has_error_label("TransientTransactionError")
                await self._end(abort=True)
                if replayable and attempt < COMMIT_ATTEMPTS:
                    continue
                self._reset()
                raise
            await self._end(abort=False)
            for doc in written:
                doc._save_state()
            self._new.clear()
            self._deleted.clear()
            return

    async def rollback(self) -> None:
        """Discard pending changes and abort the transaction. Tracked documents are forgotten (they may hold
        changes that were never saved), like SQLAlchemy expiring them."""
        await self._end(abort=True)
        self._reset()

    def _reset(self) -> None:
        self._identity.clear()
        self._new.clear()
        self._deleted.clear()

    async def _end(self, abort: bool) -> None:
        txn, self._txn, self._sent = self._txn, None, False
        if txn is None:
            return
        try:
            if abort and txn.in_transaction:
                await txn.abort_transaction()
        finally:
            await txn.end_session()

    async def close(self) -> None:
        await self._end(abort=True)


@asynccontextmanager
async def mongo_session() -> AsyncIterator[Session]:
    session = Session()
    try:
        yield session
    finally:
        await session.close()


async def get_mongo_db() -> AsyncIterator[Session]:
    async with mongo_session() as session:
        yield session


def is_transient(exc: BaseException) -> bool:
    return isinstance(exc, PyMongoError) and exc.has_error_label("TransientTransactionError")


async def retry_transient[T](db: Session, work: Callable[[], Awaitable[T]], attempts: int = 4) -> T:
    """Run ``work`` (which uses ``db`` and commits) again after a write conflict with a concurrent transaction.

    MongoDB aborts the later of two transactions writing the same document instead of making it wait as PostgreSQL
    does, so contended writes (reserving a node's capacity, a wallet's balance) are retried here. ``work`` must have
    no side effects outside the database before it commits, and must load the documents it changes itself: the
    rollback before a retry forgets everything the session had loaded.
    """
    for attempt in range(1, attempts + 1):
        try:
            return await work()
        except PyMongoError as exc:
            if not is_transient(exc) or attempt == attempts:
                raise
            await db.rollback()
            await asyncio.sleep(random.uniform(0, 0.02 * attempt))
    raise AssertionError("unreachable")
