import asyncio
import logging

import httpx

from ..deployment.tracker import DeploymentTracker

logger = logging.getLogger(__name__)


class UsageReporter:
    def __init__(self, control_plane_url: str, api_key: str, interval: int, tracker: DeploymentTracker):
        self.control_plane_url = control_plane_url
        self.api_key = api_key
        self.interval = interval
        self.tracker = tracker
        self.running = False
        self.task = None

    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._loop())
        logger.info("Usage reporter started")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        async with httpx.AsyncClient() as client:
            while self.running:
                await asyncio.sleep(self.interval)
                for deployment_id in list(self.tracker._usage.keys()):
                    usage = self.tracker.get_usage(deployment_id)
                    try:
                        await self._report_usage(client, deployment_id, usage)
                    except Exception as e:
                        logger.error(f"Failed to report usage for {deployment_id}: {e}")

    async def _report_usage(self, client, deployment_id: str, usage):
        payload = {
            "gpu_seconds": usage.gpu_seconds,
            "cpu_seconds": usage.cpu_seconds,
            "memory_mb_hours": usage.memory_mb_hours,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        resp = await client.post(
            f"{self.control_plane_url}/api/v1/deployments/{deployment_id}/usage",
            json=payload,
            headers=headers,
            timeout=5.0,
        )
        resp.raise_for_status()
