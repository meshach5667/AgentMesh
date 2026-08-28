import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_deployments(client: AsyncClient, auth_headers):
    response = await client.get("/api/v1/deployments", headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_deployment_invalid_data(client: AsyncClient, auth_headers):
    response = await client.post("/api/v1/deployments", headers=auth_headers, json={})
    assert response.status_code == 422
