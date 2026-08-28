import asyncio
from dataclasses import dataclass

from ..runtime.base import ModelRuntime


@dataclass
class UsageData:
    gpu_seconds: float
    cpu_seconds: float
    memory_mb_hours: float


class DeploymentTracker:
    def __init__(self, runtime: ModelRuntime):
        self.runtime = runtime
        self._tracking: dict[str, asyncio.Task] = {}
        self._usage: dict[str, UsageData] = {}

    def start_tracking(self, deployment_id: str, container_id: str):
        if deployment_id in self._tracking:
            return
        self._usage[deployment_id] = UsageData(0.0, 0.0, 0.0)
        self._tracking[deployment_id] = asyncio.create_task(self._track_loop(deployment_id, container_id))

    def stop_tracking(self, deployment_id: str):
        if deployment_id in self._tracking:
            self._tracking[deployment_id].cancel()
            del self._tracking[deployment_id]

    async def _track_loop(self, deployment_id: str, container_id: str):
        try:
            while True:
                await asyncio.sleep(10)
                metrics = await self.runtime.get_metrics(container_id)
                usage = self._usage.get(deployment_id)
                if usage:
                    # simplistic approximation
                    usage.cpu_seconds += (metrics.cpu_usage / 100.0) * 10
                    usage.memory_mb_hours += metrics.memory_usage * (10 / 3600.0)
        except asyncio.CancelledError:
            pass

    def get_usage(self, deployment_id: str) -> UsageData:
        return self._usage.get(deployment_id, UsageData(0.0, 0.0, 0.0))
