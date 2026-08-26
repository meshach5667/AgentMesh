import asyncio
from app.core.config import settings

async def usage_collector_loop():
    while True:
        await asyncio.sleep(60)
        # Collect usage and bill
