import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
import pytest_asyncio
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from httpx import ASGITransport, AsyncClient, Response
import httpx
from jose import jwt

from app.core.config import settings
from app.dependencies import get_current_user
from app.main import app
from app.models.user import User

_test_bearer = HTTPBearer(auto_error=False)


async def test_get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_test_bearer),
) -> User:
    """Offline test dependency override for get_current_user."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    if token == "mock-ecc-valid-token":
        return User(
            id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
            auth_user_id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
            email="ecc_user@moderngebeya.com",
            full_name="ECC Admin",
            role="ADMIN",
            is_active=True,
        )

    if token == "mock-ecc-unprovisioned-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account inactive or not provisioned in application directory.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = settings.SUPABASE_JWT_SECRET or settings.JWT_SECRET
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token: missing sub claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = payload.get("role", "ADMIN")
    email = payload.get("email", f"{sub}@example.com")
    full_name = payload.get("full_name", f"Test {role}")

    try:
        user_uuid = uuid.UUID(str(sub))
    except Exception:
        user_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, str(sub))

    return User(
        id=user_uuid,
        auth_user_id=user_uuid,
        email=email,
        full_name=full_name,
        role=role,
        is_active=True,
    )


@pytest.fixture(autouse=True)
def override_auth_dependency():
    """Overrides get_current_user on the FastAPI app for offline testing."""
    app.dependency_overrides[get_current_user] = test_get_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


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
