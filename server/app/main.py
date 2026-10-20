import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.background.monitors import monitor_loop
from app.core.config import settings
from app.core.exceptions import AgentMeshException, agentmesh_exception_handler
from app.core.logging import setup_logging
from app.core.middleware import BodySizeLimitMiddleware

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start background tasks on startup, clean up on shutdown."""
    logger.info("AgentMesh API starting up...")
    tasks = []
    if settings.BACKGROUND_JOBS_ENABLED:
        tasks.append(asyncio.create_task(monitor_loop()))
        logger.info("Background monitors started")
    yield
    logger.info("AgentMesh API shutting down...")
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="AgentMesh API",
    description="Decentralized AI Compute Marketplace - Control Plane API",
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
app.add_exception_handler(AgentMeshException, agentmesh_exception_handler)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "agentmesh-api", "version": "0.1.0"}
