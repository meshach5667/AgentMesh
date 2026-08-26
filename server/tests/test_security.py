import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_invalid_token(client: AsyncClient):
    headers = {"Authorization": "Bearer invalid_token"}
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_node_api_key_validation(client: AsyncClient):
    headers = {"X-Node-API-Key": "invalid_key"}
    response = await client.post("/api/v1/nodes/heartbeat", headers=headers, json={})
    assert response.status_code == 401
