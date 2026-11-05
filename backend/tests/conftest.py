import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient, ASGITransport, Response
import httpx
from jose import jwt

from app.core.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def mock_supabase_auth_network(monkeypatch):
    """
    Mocks external network calls to Supabase Auth (/auth/v1/user) during test execution.
    Returns 401 for standard test tokens so local decode fallback runs instantly,
    or returns 200 with mock user data for ECC test tokens.
    """
    original_get = httpx.AsyncClient.get

    async def mock_get(self, url, *args, **kwargs):
        url_str = str(url)
        if "/auth/v1/user" in url_str:
            headers = kwargs.get("headers") or {}
            auth_header = headers.get("Authorization", "")
            if "mock-ecc-valid" in auth_header:
                return Response(
                    200,
                    json={
                        "id": "11111111-2222-3333-4444-555555555555",
                        "email": "ecc_user@moderngebeya.com",
                        "user_metadata": {
                            "role": "ADMIN",
                            "full_name": "ECC Admin",
                        },
                    },
                )
            if "mock-ecc-unprovisioned" in auth_header:
                return Response(
                    200,
                    json={
                        "id": "99999999-9999-9999-9999-999999999999",
                        "email": "unregistered@example.com",
                        "user_metadata": {},
                    },
                )
            return Response(401, json={"message": "Invalid or expired token"})

        return await original_get(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)


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
