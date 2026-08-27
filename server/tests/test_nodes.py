import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_list_nodes_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/nodes")
    assert response.status_code == 401
