import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import AgentMeshException, agentmesh_exception_handler
from app.background.heartbeat_monitor import heartbeat_monitor_loop
from app.background.usage_collector import usage_collector_loop
from app.background.deployment_monitor import deployment_monitor_loop
import logging

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start background tasks on startup, clean up on shutdown."""
    logger.info("AgentMesh API starting up...")
    tasks = []
    try:
        tasks.append(asyncio.create_task(heartbeat_monitor_loop()))
        tasks.append(asyncio.create_task(usage_collector_loop()))
        tasks.append(asyncio.create_task(deployment_monitor_loop()))
        logger.info("Background tasks started")
    except Exception as e:
        logger.warning(f"Could not start background tasks: {e}")
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

app.add_exception_handler(AgentMeshException, agentmesh_exception_handler)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "agentmesh-api", "version": "0.1.0"}
