import asyncio
from app.core.config import settings

async def deployment_monitor_loop():
    while True:
        await asyncio.sleep(60)
        # Check deployments
