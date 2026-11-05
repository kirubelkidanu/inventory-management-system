import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient, ASGITransport
from jose import jwt

from app.core.config import settings
from app.main import app


@pytest.fixture
def make_test_token():
    def _make(role: str = "ADMIN", user_id: str = "user-123", email: str = "user@example.com") -> str:
        secret = settings.SUPABASE_JWT_SECRET or settings.JWT_SECRET
        return jwt.encode(
            {
                "sub": user_id,
                "email": email,
                "role": role,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            },
            secret,
            algorithm=settings.JWT_ALGORITHM,
        )
    return _make


@pytest.fixture
def token_factory(make_test_token):
    return make_test_token


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
