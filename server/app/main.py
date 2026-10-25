import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from app.api import ops
from app.api.ops import SecurityHeadersMiddleware
from app.api.router import api_router
from app.background.monitors import monitor_loop
from app.core.config import settings
from app.core.database import session_scope
from app.core.exceptions import AgentMeshException, agentmesh_exception_handler
from app.core.logging import RequestIdMiddleware, setup_logging
from app.core.middleware import BodySizeLimitMiddleware
from app.core.mongo import close_mongo, init_mongo
from app.services.catalog_seed import seed_catalog

setup_logging(settings.LOG_LEVEL, settings.LOG_JSON)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start background tasks on startup, clean up on shutdown."""
    logger.info("AgentMesh API starting up...")
    await init_mongo()  # creates missing collections and indexes
    async with session_scope() as db:
        added = await seed_catalog(db)
    if added:
        logger.info("Added %d built-in catalog entries", added)
    tasks = []
    coordinator = None
    redis = None
    if settings.COORDINATION_BACKEND == "redis":
        from redis.asyncio import from_url

        from app.core.ratelimit import limiters
        from app.services.tunnel import RedisCoordinator, broker

        redis = from_url(settings.REDIS_URL, decode_responses=True)
        await redis.ping()
        limiters.use_redis(redis)
        coordinator = RedisCoordinator(redis, broker)
        broker.coordinator = coordinator
        await coordinator.start()
        logger.info("Redis coordination enabled (replica %s)", coordinator.replica_id)
    if settings.BACKGROUND_JOBS_ENABLED:
        tasks.append(asyncio.create_task(monitor_loop(redis)))
        logger.info("Background monitors started")
    yield
    logger.info("AgentMesh API shutting down...")
    if coordinator is not None:
        await coordinator.stop()
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await close_mongo()


app = FastAPI(
    title="AgentMesh API",
    description="AgentMesh control plane: deployments, inference gateway, worker protocol, billing",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    BodySizeLimitMiddleware,
    limits={f"{settings.API_V1_PREFIX}/worker": settings.WORKER_MAX_BODY_BYTES},
    default_limit=settings.GATEWAY_MAX_BODY_BYTES + 64 * 1024,
)
app.add_middleware(RequestIdMiddleware)
app.add_exception_handler(AgentMeshException, agentmesh_exception_handler)  # type: ignore[arg-type]


@app.exception_handler(PyMongoError)
async def database_error_handler(request: Request, exc: PyMongoError):
    # MongoDB aborts a transaction that touched a document another transaction changed (PostgreSQL would wait);
    # nothing was saved, so the client can simply retry.
    if exc.has_error_label("TransientTransactionError"):
        return JSONResponse(
            status_code=409,
            content={"detail": "A concurrent change conflicted with this request; nothing was saved. Retry it."},
        )
    raise exc


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(ops.router)

app.add_middleware(SecurityHeadersMiddleware)
