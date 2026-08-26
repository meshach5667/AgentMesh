import asyncio
import httpx
import logging
import time
from ..metrics.collector import MetricsCollector

logger = logging.getLogger(__name__)

class HeartbeatService:
    def __init__(self, control_plane_url: str, node_id: str, api_key: str, interval: int, metrics_collector: MetricsCollector = None):
        self.control_plane_url = control_plane_url
        self.node_id = node_id
        self.api_key = api_key
        self.interval = interval
        self.running = False
        self.task = None
        self.metrics_collector = metrics_collector or MetricsCollector()
        
    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._loop())
        logger.info(f"Heartbeat service started for node {self.node_id}")
        
    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat service stopped")
            
    async def _loop(self):
        async with httpx.AsyncClient() as client:
            while self.running:
                try:
                    await self._send_heartbeat(client)
                except Exception as e:
                    logger.error(f"Failed to send heartbeat: {e}")
                
                await asyncio.sleep(self.interval)
                
    async def _send_heartbeat(self, client):
        metrics_summary = self.metrics_collector.get_summary()
        payload = {
            "status": "online",
            "metrics_summary": metrics_summary,
            "active_deployments_count": 0, # To be integrated with deployment manager
            "timestamp": time.time()
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        response = await client.post(
            f"{self.control_plane_url}/api/v1/nodes/{self.node_id}/heartbeat",
            json=payload,
            headers=headers,
            timeout=5.0
        )
        response.raise_for_status()
