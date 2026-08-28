import asyncio


async def deployment_monitor_loop():
    while True:
        await asyncio.sleep(60)
        # Check deployments
