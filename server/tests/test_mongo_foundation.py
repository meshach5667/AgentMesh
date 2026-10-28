"""MongoDB foundation: documents, indexes, value encoding, and the unit-of-work Session."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from bson import Binary, Decimal128
from bson.binary import UUID_SUBTYPE
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core import mongo as mongo_core
from app.core.mongo import Session
from app.core.timeutil import utcnow
from app.documents import DOCUMENTS, CostEstimate, Deployment, Node, ResourceReservation, User


def _user(email="a@example.com") -> User:
    return User(email=email, hashed_password="x", role="customer")


def _node(**kw) -> Node:
    return Node(**{"owner_id": uuid.uuid4(), "allocated_cpu_cores": 4, "allocated_ram_mb": 8192, **kw})


async def test_every_collection_and_declared_index_exists(mongo):
    names = set(await mongo.list_collection_names())
    assert {d.get_settings().name for d in DOCUMENTS} <= names
    # Beanie silently skips an index whose keys duplicate another one's, so check each declared index exists.
    for doc in DOCUMENTS:
        actual = {
            tuple(k for k, _ in spec["key"]): bool(spec.get("unique"))
            for spec in (await mongo[doc.get_settings().name].index_information()).values()
        }
        for declared in getattr(doc.Settings, "indexes", []):
            keys = tuple(declared.document["key"])
            assert actual.get(keys) == bool(declared.document.get("unique")), (doc.__name__, keys)


def _estimate(amount=Decimal("1")) -> CostEstimate:
    now = utcnow()
    return CostEstimate(
        deployment_id=uuid.uuid4(),
        period_start=now,
        period_end=now,
        resource_amount=amount,
        token_amount=Decimal(0),
        amount=amount,
        currency="NGN",
    )


async def test_unique_email(mdb):
    mdb.add(_user())
    await mdb.commit()
    mdb.add(_user())
    with pytest.raises(DuplicateKeyError):
        await mdb.commit()


async def test_nullable_unique_allows_many_nulls_like_sql(mdb):
    customer = uuid.uuid4()
    mdb.add_all([Deployment(customer_id=customer), Deployment(customer_id=customer)])
    mdb.add_all([Deployment(customer_id=customer, idempotency_key="k")])
    await mdb.commit()
    mdb.add(Deployment(customer_id=customer, idempotency_key="k"))
    with pytest.raises(DuplicateKeyError):
        await mdb.commit()


async def test_one_active_reservation_per_deployment(mdb):
    dep, node = uuid.uuid4(), uuid.uuid4()
    mdb.add_all([ResourceReservation(deployment_id=dep, node_id=node, status="RELEASED") for _ in range(2)])
    mdb.add(ResourceReservation(deployment_id=dep, node_id=node))
    await mdb.commit()
    mdb.add(ResourceReservation(deployment_id=dep, node_id=node))
    with pytest.raises(DuplicateKeyError):
        await mdb.commit()


async def test_money_and_ids_are_stored_exactly(mongo, mdb):
    estimate = _estimate(amount=Decimal("1234567890.12345678"))
    mdb.add(estimate)
    await mdb.commit()
    raw = await mongo.cost_estimates.find_one({"_id": estimate.id})
    assert isinstance(raw["amount"], Decimal128)
    assert raw["_id"] == estimate.id  # decoded as a UUID, i.e. stored as a standard BSON UUID
    stored = await mongo.cost_estimates.find_one({"_id": Binary(estimate.id.bytes, UUID_SUBTYPE)})
    assert stored is not None
    loaded = await Session().get(CostEstimate, estimate.id)
    assert loaded.amount == Decimal("1234567890.12345678")


async def test_commit_is_all_or_nothing(mdb):
    customer = uuid.uuid4()
    mdb.add(Deployment(customer_id=customer, idempotency_key="dup"))
    await mdb.commit()
    estimate = _estimate()
    mdb.add(estimate)
    mdb.add(Deployment(customer_id=customer, idempotency_key="dup"))
    with pytest.raises(DuplicateKeyError):
        await mdb.commit()
    assert await CostEstimate.get(estimate.id) is None


async def test_identity_map_and_change_tracking(mdb):
    node = _node(name="n1")
    mdb.add(node)
    await mdb.commit()

    other = Session()
    loaded = await other.get(Node, node.id)
    assert loaded is await other.get(Node, node.id)
    assert (await other.find(Node, {"name": "n1"}))[0] is loaded

    # A concurrent atomic update of another field survives saving this session's change.
    assert await mdb.update_one(Node, {"_id": node.id}, {"$inc": {"reserved_cpu_cores": 2}})
    await mdb.commit()
    loaded.name = "renamed"
    await other.commit()
    fresh = await Node.get(node.id)
    assert (fresh.name, fresh.reserved_cpu_cores) == ("renamed", 2)


async def test_updated_at_is_touched_on_change(mdb):
    node = _node()
    mdb.add(node)
    await mdb.commit()
    before = node.updated_at
    node.region = "eu"
    await mdb.commit()
    assert (await Node.get(node.id)).updated_at > before


async def test_conditional_update_and_rollback(mdb):
    node = _node()
    mdb.add(node)
    await mdb.commit()
    fits = {"_id": node.id, "$expr": {"$lte": [{"$add": ["$reserved_cpu_cores", 3]}, "$allocated_cpu_cores"]}}
    assert await mdb.update_one(Node, fits, {"$inc": {"reserved_cpu_cores": 3}})
    assert not await mdb.update_one(Node, fits, {"$inc": {"reserved_cpu_cores": 3}})  # 6 > 4 cores
    await mdb.rollback()
    assert (await Node.get(node.id)).reserved_cpu_cores == 0


async def test_flush_surfaces_duplicates_before_commit(mdb):
    mdb.add(_user())
    await mdb.commit()
    mdb.add(_user())
    with pytest.raises(DuplicateKeyError):
        await mdb.flush()
    await mdb.rollback()


async def test_refresh_reloads_but_keeps_local_changes(mdb):
    node = _node(region="us")
    mdb.add(node)
    await mdb.commit()
    node.region = "local"
    await mdb.update_one(Node, {"_id": node.id}, {"$set": {"name": "renamed"}})
    await mdb.refresh(node)
    assert node.name == "renamed" and node.region == "local"
    await mdb.commit()
    fresh = await Session().get(Node, node.id)
    assert fresh is not None and (fresh.name, fresh.region) == ("renamed", "local")


async def test_transient_conflict_is_replayed(mdb, monkeypatch):
    estimate = _estimate(amount=Decimal("5"))
    mdb.add(estimate)
    real_write, calls = Session._write, []

    async def flaky(self, txn):
        calls.append(1)
        if len(calls) == 1:
            raise PyMongoError("write conflict", error_labels=["TransientTransactionError"])
        return await real_write(self, txn)

    monkeypatch.setattr(Session, "_write", flaky)
    await mdb.commit()
    assert len(calls) == 2
    assert (await CostEstimate.get(estimate.id)).amount == Decimal("5")


async def test_not_initialised_is_an_error():
    await mongo_core.close_mongo()
    session = Session()  # creating one needs no connection; using it does
    with pytest.raises(RuntimeError):
        await session.count(Node)


def test_utcnow_is_millisecond_and_strictly_increasing():
    stamps = [utcnow() for _ in range(2000)]
    assert all(s.microsecond % 1000 == 0 for s in stamps)
    assert all(b > a for a, b in zip(stamps, stamps[1:], strict=False))
    assert stamps[-1] - stamps[0] < timedelta(seconds=10)


async def test_find_sort_skip_limit_and_count(mdb):
    mdb.add_all([_node(name=f"n{i}", allocated_ram_mb=1000 * i) for i in range(5)])
    await mdb.commit()
    page = await mdb.find(Node, {"allocated_ram_mb": {"$gte": 1000}}, sort=[("allocated_ram_mb", -1)], skip=1, limit=2)
    assert [n.name for n in page] == ["n3", "n2"]
    assert await mdb.count(Node, {"allocated_ram_mb": {"$gte": 1000}}) == 4
    assert (await mdb.find_one(Node, sort=[("allocated_ram_mb", 1)])).name == "n0"


async def test_queries_and_updates_autoflush_pending_changes(mdb):
    node = _node(region="eu")
    mdb.add(node)
    assert await mdb.count(Node, {"region": "eu"}) == 1
    node.region = "us"
    assert [n.id for n in await mdb.find(Node, {"region": "us"})] == [node.id]
    assert await mdb.update_one(Node, {"_id": node.id, "region": "us"}, {"$set": {"name": "n1"}})
    await mdb.rollback()
    assert await Session().count(Node) == 0


async def test_catalog_seed_adds_missing_entries_once_and_keeps_operator_changes(mdb):
    from app.documents import Model, ModelArtifact
    from app.services.catalog_seed import CATALOG, HF_ARTIFACTS, NEW_MODELS, model_id, seed_catalog

    added = await seed_catalog(mdb)
    assert await mdb.count(Model) == len(CATALOG) + len(NEW_MODELS)
    assert await mdb.count(ModelArtifact) == len(CATALOG) + len(HF_ARTIFACTS)
    assert added == await mdb.count(Model) + await mdb.count(ModelArtifact)

    withdrawn = await mdb.get(Model, model_id("smollm2:135m"))
    withdrawn.is_approved = False
    await mdb.commit()
    assert await seed_catalog(mdb) == 0
    mdb.expire_all()
    assert (await mdb.get(Model, model_id("smollm2:135m"))).is_approved is False


async def test_replicas_starting_at_once_on_an_empty_database_all_start(mongodb_url):
    """Several API replicas run init_mongo concurrently on first deploy; none may fail on a collection another one
    created a moment earlier (CollectionInvalid) or on its indexes."""
    import asyncio

    from app.documents import Model
    from app.services.catalog_seed import catalog_models, seed_catalog

    db_name = f"race_{uuid.uuid4().hex[:8]}"
    clients = await asyncio.gather(*(mongo_core.init_mongo(mongodb_url, db_name) for _ in range(4)))
    try:
        names = set(await clients[0][db_name].list_collection_names())
        assert {d.get_settings().name for d in DOCUMENTS} <= names

        # Each replica is its own process with one client; here they share one, seeding in separate transactions.
        clients.append(await mongo_core.init_mongo(mongodb_url, db_name))

        async def seed() -> int:
            async with mongo_core.mongo_session() as s:
                return await seed_catalog(s)

        added = await asyncio.gather(*(seed() for _ in range(4)))  # every replica seeds the catalog at startup
        async with mongo_core.mongo_session() as s:
            assert await s.count(Model) == len(catalog_models())
        assert sum(added) >= len(catalog_models())  # someone inserted them; nobody crashed
    finally:
        await clients[0].drop_database(db_name)
        for c in clients:
            await c.close()
