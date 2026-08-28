import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_wallet_balance(client: AsyncClient, auth_headers):
    response = await client.get("/api/v1/wallet", headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_deposit_funds(client: AsyncClient, auth_headers):
    response = await client.post("/api/v1/wallet/deposit", headers=auth_headers, json={"amount": 50.0})
    assert response.status_code == 200
    assert "transaction_id" in response.json()
