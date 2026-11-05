import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import settings
from app.main import app
from app.dependencies import get_current_user, require_role, require_roles
from app.models.user import User


@pytest.fixture
def protected_app():
    api = FastAPI()

    @api.get("/protected")
    async def protected(user: User = Depends(get_current_user)):
        return {"user_id": user.user_id, "email": user.email, "role": user.role}

    @api.get("/role-protected")
    async def role_protected(
        user: User = Depends(require_role("ADMIN", "INVENTORY_MANAGER"))
    ):
        return {"user_id": user.user_id, "role": user.role}

    return api


@pytest.mark.asyncio
async def test_health_remains_public():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_missing_authorization_header_fails(protected_app):
    async with AsyncClient(transport=ASGITransport(app=protected_app), base_url="http://test") as client:
        response = await client.get("/protected")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_bearer_format_fails(protected_app):
    async with AsyncClient(transport=ASGITransport(app=protected_app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": "Basic abc"})
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_token_fails(protected_app):
    async with AsyncClient(transport=ASGITransport(app=protected_app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": "Bearer not-a-valid-token"})
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower() or "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_valid_token_succeeds(protected_app):
    secret = settings.SUPABASE_JWT_SECRET or settings.JWT_SECRET
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": "user@example.com",
            "role": "ADMIN",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        secret,
        algorithm=settings.JWT_ALGORITHM,
    )

    async with AsyncClient(transport=ASGITransport(app=protected_app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"
    assert response.json()["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_expired_token_fails(protected_app):
    secret = settings.SUPABASE_JWT_SECRET or settings.JWT_SECRET
    expired = jwt.encode(
        {
            "sub": "expired-user",
            "email": "expired@example.com",
            "role": "VIEWER",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        secret,
        algorithm=settings.JWT_ALGORITHM,
    )

    async with AsyncClient(transport=ASGITransport(app=protected_app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_role_check_fails_when_user_is_not_allowed(protected_app):
    secret = settings.SUPABASE_JWT_SECRET or settings.JWT_SECRET
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": "viewer@example.com",
            "role": "VIEWER",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        secret,
        algorithm=settings.JWT_ALGORITHM,
    )

    async with AsyncClient(transport=ASGITransport(app=protected_app), base_url="http://test") as client:
        response = await client.get("/role-protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


# ===========================================================================
# Strict Supabase JWT & GET /api/v1/auth/me Verification
# ===========================================================================

@pytest.mark.asyncio
async def test_auth_me_without_authorization_header_returns_401():
    """1. GET /api/v1/auth/me without Authorization header returns HTTP 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_me_with_invalid_or_expired_token_returns_401():
    """2. GET /api/v1/auth/me with invalid/expired token returns HTTP 401."""
    secret = settings.SUPABASE_JWT_SECRET or settings.JWT_SECRET

    # Invalid signature / format
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_invalid = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.mock.jwt"},
        )
    assert res_invalid.status_code == 401

    # Expired token
    expired_token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": "expired@example.com",
            "role": "ADMIN",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=10),
        },
        secret,
        algorithm=settings.JWT_ALGORITHM,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_expired = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
    assert res_expired.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_with_valid_jwt_returns_profile():
    """3. GET /api/v1/auth/me with valid JWT returns user profile with role."""
    secret = settings.SUPABASE_JWT_SECRET or settings.JWT_SECRET
    user_id = str(uuid.uuid4())
    valid_token = jwt.encode(
        {
            "sub": user_id,
            "email": "auditor@moderngebeya.com",
            "role": "STORE_KEEPER",
            "full_name": "Auditor Keeper",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        secret,
        algorithm=settings.JWT_ALGORITHM,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "STORE_KEEPER"
    assert data["email"] == "auditor@moderngebeya.com"
    assert "id" in data
    assert "auth_user_id" in data
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_role_guarded_endpoint_returns_403_for_non_admin(token_factory):
    """4. Role-guarded endpoint (POST /api/v1/categories) returns HTTP 403 when called with non-admin role."""
    viewer_token = token_factory(role="VIEWER")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/categories",
            json={"code": "TEST-CAT-FORBIDDEN", "name": "Forbidden Category"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


# ===========================================================================
# Supabase ECC (P-256) / ES256 Auth API Verification Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_auth_me_with_supabase_ecc_token_verifies_via_auth_api():
    """Validates that Supabase ECC (P-256) asymmetric tokens verified via /auth/v1/user return authenticated profile."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer mock-ecc-valid-token"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "ecc_user@moderngebeya.com"
    assert data["role"] == "ADMIN"
    assert data["full_name"] == "ECC Admin"


@pytest.mark.asyncio
async def test_auth_me_with_supabase_ecc_token_not_provisioned_in_db_returns_401():
    """Validates that a valid Supabase token for an unprovisioned user returns HTTP 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer mock-ecc-unprovisioned-token"},
        )

    assert response.status_code == 401
    assert "not provisioned" in response.json()["detail"].lower()
