import asyncio


async def usage_collector_loop():
    while True:
        await asyncio.sleep(60)
        # Collect usage and bill
