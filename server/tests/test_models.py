import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_models(client: AsyncClient):
    response = await client.get("/api/v1/models")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_model_unauthorized(client: AsyncClient):
    response = await client.post("/api/v1/models", json={"name": "test-model"})
    assert response.status_code in [401, 403]
