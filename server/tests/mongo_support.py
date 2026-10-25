"""MongoDB test fixtures.

Tests run against TEST_MONGODB_URL when it is set (CI points it at a MongoDB service). Otherwise a private
single-node replica set is started from the local ``mongod`` binary, on a free port with a temporary data
directory, and stopped after the test session; a system MongoDB service is never used. Without either, the tests
that need MongoDB are skipped. Each test starts with an empty database.
"""

import os
import shutil
import socket
import subprocess
import time
import uuid

import pytest
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.core import mongo as mongo_core


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def mongodb_url(tmp_path_factory):
    if url := os.environ.get("TEST_MONGODB_URL"):
        yield url
        return
    binary = shutil.which("mongod")
    if binary is None:
        pytest.skip("MongoDB tests need TEST_MONGODB_URL or a local mongod binary")
    port = _free_port()
    data = tmp_path_factory.mktemp("mongod")
    proc = subprocess.Popen(
        [binary, "--replSet", "rs0", "--port", str(port), "--bind_ip", "127.0.0.1", "--dbpath", str(data),
         "--wiredTigerCacheSizeGB", "0.25", "--quiet", "--logpath", str(data / "mongod.log")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )  # fmt: skip
    try:
        admin = MongoClient(f"mongodb://127.0.0.1:{port}/?directConnection=true", serverSelectionTimeoutMS=500)
        deadline = time.monotonic() + 30
        initiated = False
        while True:
            try:
                if not initiated:
                    admin.admin.command(
                        "replSetInitiate", {"_id": "rs0", "members": [{"_id": 0, "host": f"127.0.0.1:{port}"}]}
                    )
                    initiated = True
                if admin.admin.command("hello").get("isWritablePrimary"):
                    break
            except PyMongoError:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError(f"mongod did not become primary; see {data / 'mongod.log'}")
            time.sleep(0.2)
        admin.close()
        yield f"mongodb://127.0.0.1:{port}/?replicaSet=rs0"
    finally:
        proc.terminate()
        proc.wait(timeout=30)


@pytest.fixture(scope="session")
def mongo_db_name(mongodb_url):
    """One database per test session (creating collections and indexes for every test is slow); it is emptied
    after each test and dropped at the end."""
    name = f"agentmesh_test_{uuid.uuid4().hex[:12]}"
    yield name
    client = MongoClient(mongodb_url)
    client.drop_database(name)
    client.close()


@pytest.fixture
async def mongo(mongodb_url, mongo_db_name):
    """An empty database with every document registered and its indexes created."""
    client = await mongo_core.init_mongo(mongodb_url, mongo_db_name)
    database = client[mongo_db_name]
    yield database
    for name in await database.list_collection_names():
        await database[name].delete_many({})
    await mongo_core.close_mongo()


@pytest.fixture
async def mdb(mongo):
    async with mongo_core.mongo_session() as session:
        yield session
