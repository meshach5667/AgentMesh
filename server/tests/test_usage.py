import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_usage(client: AsyncClient, auth_headers):
    response = await client.get("/api/v1/usage", headers=auth_headers)
    assert response.status_code in [200, 401]
