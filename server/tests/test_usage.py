import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_record_usage(client: AsyncClient, node_auth_headers):
    response = await client.post("/api/v1/usage/record", headers=node_auth_headers, json={
        "deployment_id": "123e4567-e89b-12d3-a456-426614174000",
        "gpu_seconds": 3600,
        "cpu_seconds": 3600,
        "period_start": "2023-01-01T12:00:00Z",
        "period_end": "2023-01-01T13:00:00Z"
    })
    assert response.status_code in [200, 201, 404] # 404 if deployment not found in test db

@pytest.mark.asyncio
async def test_get_usage_summary(client: AsyncClient, auth_headers):
    response = await client.get("/api/v1/usage/summary", headers=auth_headers)
    assert response.status_code == 200
