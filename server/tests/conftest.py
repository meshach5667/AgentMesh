import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from app.main import app
from app.core.security import create_access_token
from app.models.user import UserRole

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def auth_headers():
    test_user_id = str(uuid.uuid4())
    token = create_access_token(test_user_id)
    return {"Authorization": f"Bearer {token}"}
