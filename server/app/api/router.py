from fastapi import APIRouter

from app.api.v1 import agent, auth, deployments, earnings, marketplace, models, nodes, transactions, usage, wallets

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(nodes.router, prefix="/nodes", tags=["nodes"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(deployments.router, prefix="/deployments", tags=["deployments"])
api_router.include_router(marketplace.router, prefix="/marketplace", tags=["marketplace"])
api_router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(earnings.router, prefix="/earnings", tags=["earnings"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
