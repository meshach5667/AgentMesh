from fastapi import APIRouter

from app.api.v1 import (
    agent,
    api_keys,
    auth,
    deployments,
    earnings,
    gateway,
    marketplace,
    models,
    nodes,
    transactions,
    usage,
    wallets,
    worker,
    workloads,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(nodes.router, prefix="/nodes", tags=["nodes"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(deployments.router, prefix="/deployments", tags=["deployments"])
api_router.include_router(gateway.router, prefix="/deployments", tags=["inference gateway"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api keys"])
api_router.include_router(worker.router, prefix="/worker", tags=["worker protocol v1"])
api_router.include_router(marketplace.router, prefix="/marketplace", tags=["marketplace"])
api_router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(earnings.router, prefix="/earnings", tags=["earnings"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(workloads.router, tags=["workloads"])
