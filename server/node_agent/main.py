import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

import node_agent.api.routes as api_routes_module

from .api.routes import router as api_router
from .config import settings
from .deployment.manager import DeploymentManager
from .deployment.tracker import DeploymentTracker
from .heartbeat.service import HeartbeatService
from .metrics.collector import MetricsCollector
from .registration import load_registration
from .runtime.ollama import OllamaRuntime
from .runtime.vllm import VLLMRuntime
from .usage.reporter import UsageReporter

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

heartbeat_service = None
usage_reporter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global heartbeat_service, usage_reporter

    node_id, api_key = load_registration()
    if not node_id:
        logger.warning("Node not registered. Start node_agent register first.")
    else:
        metrics_collector = MetricsCollector()

        runtime = (
            VLLMRuntime(settings.DOCKER_SOCKET)
            if settings.DEFAULT_RUNTIME == "vllm"
            else OllamaRuntime(settings.DOCKER_SOCKET)
        )
        deployment_manager = DeploymentManager(runtime)
        deployment_tracker = DeploymentTracker(runtime)

        api_routes_module.deployment_manager = deployment_manager
        api_routes_module.metrics_collector = metrics_collector
        api_routes_module.settings = settings

        heartbeat_service = HeartbeatService(
            control_plane_url=settings.CONTROL_PLANE_URL,
            node_id=node_id,
            api_key=api_key,
            interval=settings.HEARTBEAT_INTERVAL_SECONDS,
            metrics_collector=metrics_collector,
        )
        await heartbeat_service.start()

        usage_reporter = UsageReporter(
            control_plane_url=settings.CONTROL_PLANE_URL,
            api_key=api_key,
            interval=settings.USAGE_REPORT_INTERVAL_SECONDS,
            tracker=deployment_tracker,
        )
        await usage_reporter.start()

    yield

    if heartbeat_service:
        await heartbeat_service.stop()
    if usage_reporter:
        await usage_reporter.stop()


app = FastAPI(title="AgentMesh Node Agent", lifespan=lifespan)
app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run(app, host=settings.NODE_AGENT_HOST, port=settings.NODE_AGENT_PORT)
