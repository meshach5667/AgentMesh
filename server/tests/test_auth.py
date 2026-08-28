import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_login_invalid(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login", data={"username": "nonexistent@example.com", "password": "wrongpassword"}
    )
    assert response.status_code in [400, 401, 422]
