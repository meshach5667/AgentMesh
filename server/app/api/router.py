from fastapi import APIRouter

from app.api.v1 import (
    admin,
    ai,
    api_keys,
    auth,
    billing,
    deployments,
    gateway,
    models,
    nodes,
    providers,
    sponsored,
    stats,
    usage,
    worker,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["operator"])
api_router.include_router(nodes.router, prefix="/nodes", tags=["nodes"])
api_router.include_router(providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(deployments.router, prefix="/deployments", tags=["deployments"])
api_router.include_router(gateway.router, prefix="/deployments", tags=["inference gateway"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api keys"])
api_router.include_router(worker.router, prefix="/worker", tags=["worker protocol v1"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai deployment agent"])
api_router.include_router(sponsored.router, prefix="/sponsored", tags=["sponsored placements"])
