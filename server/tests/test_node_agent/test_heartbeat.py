from unittest.mock import AsyncMock, patch

import pytest

from node_agent.heartbeat.service import HeartbeatService
from node_agent.metrics.collector import MetricsCollector


@pytest.mark.asyncio
async def test_heartbeat_service():
    collector = MetricsCollector()
    service = HeartbeatService("http://test", "node1", "key", 1, collector)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.raise_for_status = AsyncMock()
        await service.start()
        await service.stop()
