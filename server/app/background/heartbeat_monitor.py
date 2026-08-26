import asyncio
from app.core.config import settings

async def heartbeat_monitor_loop():
    while True:
        await asyncio.sleep(30)
        # Check node heartbeats
