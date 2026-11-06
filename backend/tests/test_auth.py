import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
import httpx
from httpx import ASGITransport, AsyncClient, Response
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


@pytest.mark.asyncio
async def test_get_current_user_auto_links_user_by_email(monkeypatch):
    """Directly tests that get_current_user auto-links an existing user profile when email matches."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.security import HTTPAuthorizationCredentials
    from httpx import Response

    new_sub = uuid.uuid4()
    mock_resp = Response(
        200,
        json={"id": str(new_sub), "email": "manager@ims.local", "user_metadata": {}},
    )
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=mock_resp))

    mock_db = AsyncMock()
    existing_user = User(
        id=uuid.uuid4(),
        auth_user_id=uuid.uuid4(),
        email="manager@ims.local",
        full_name="Existing Manager",
        role="INVENTORY_MANAGER",
        is_active=False,
    )
    res_none = MagicMock()
    res_none.scalar_one_or_none.return_value = None
    res_user = MagicMock()
    res_user.scalar_one_or_none.return_value = existing_user

    mock_db.execute = AsyncMock(side_effect=[res_none, res_user])
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="supabase-test-link-token")
    user = await get_current_user(credentials=creds, db=mock_db)

    assert user.auth_user_id == new_sub
    assert user.is_active is True
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_current_user_auto_provisions_admin_sabelkidanu(monkeypatch):
    """Directly tests that get_current_user auto-provisions sabelkidanu@gmail.com as ADMIN."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.security import HTTPAuthorizationCredentials
    from httpx import Response

    new_sub = uuid.uuid4()
    mock_resp = Response(
        200,
        json={"id": str(new_sub), "email": "sabelkidanu@gmail.com", "user_metadata": {}},
    )
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=mock_resp))

    mock_db = AsyncMock()
    res_none = MagicMock()
    res_none.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(side_effect=[res_none, res_none])
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="supabase-test-admin-token")
    user = await get_current_user(credentials=creds, db=mock_db)

    assert user.email == "sabelkidanu@gmail.com"
    assert user.role == "ADMIN"
    assert user.full_name == "Sabel Kidanu"
    assert user.auth_user_id == new_sub
    assert user.is_active is True
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_current_user_jwks_es256_verification(monkeypatch):
    """Tests Tier 2 JWKS ES256 verification when Tier 1 HTTP check fails."""
    from unittest.mock import AsyncMock, MagicMock
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    from fastapi.security import HTTPAuthorizationCredentials
    from jose import jwk, jwt

    # 1. Generate an EC key pair
    priv = ec.generate_private_key(ec.SECP256R1())
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_jwk = jwk.construct(priv.public_key(), algorithm="ES256").to_dict()
    pub_jwk["kid"] = "jwks-test-kid"

    user_sub = uuid.uuid4()
    es256_token = jwt.encode(
        {
            "sub": str(user_sub),
            "email": "jwks_user@example.com",
            "role": "ADMIN",
            "full_name": "JWKS Admin",
        },
        priv_pem,
        algorithm="ES256",
        headers={"kid": "jwks-test-kid"},
    )

    # 2. Mock Tier 1 HTTP call to fail (e.g. 500 error)
    mock_resp = httpx.Response(500, text="Internal Server Error")
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=mock_resp))

    # 3. Mock get_supabase_jwks to return our test JWK
    import app.dependencies as deps
    monkeypatch.setattr(deps, "get_supabase_jwks", AsyncMock(return_value={"keys": [pub_jwk]}))

    mock_db = AsyncMock()
    existing_user = User(
        id=user_sub,
        auth_user_id=user_sub,
        email="jwks_user@example.com",
        full_name="JWKS Admin",
        role="ADMIN",
        is_active=True,
    )
    res_user = MagicMock()
    res_user.scalar_one_or_none.return_value = existing_user
    mock_db.execute = AsyncMock(return_value=res_user)

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=es256_token)
    user = await get_current_user(credentials=creds, db=mock_db)

    assert user.email == "jwks_user@example.com"
    assert user.role == "ADMIN"
    assert user.auth_user_id == user_sub


@pytest.mark.asyncio
async def test_get_current_user_auto_provisions_admin_by_uuid(monkeypatch):
    """Directly tests that get_current_user auto-provisions when sub is the production admin UUID."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.security import HTTPAuthorizationCredentials

    admin_uuid = uuid.UUID("d3a1107b-b5a6-45bc-bcb2-981feb537d06")
    mock_resp = httpx.Response(
        200,
        json={"id": str(admin_uuid), "email": "admin-alias@moderngebeya.com", "user_metadata": {}},
    )
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=mock_resp))

    mock_db = AsyncMock()
    res_none = MagicMock()
    res_none.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(side_effect=[res_none, res_none])
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="supabase-admin-token")
    user = await get_current_user(credentials=creds, db=mock_db)

    assert user.role == "ADMIN"
    assert user.auth_user_id == admin_uuid
    assert user.is_active is True
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_current_user_all_tiers_failed_includes_diagnostics():
    """Tests that when all token verification tiers fail, HTTP 401 includes diagnostic details."""
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token-xyz")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=None)

    assert exc_info.value.status_code == 401
    assert "Diagnostics: [Tier 1" in exc_info.value.detail
    assert "Tier 2" in exc_info.value.detail
    assert "Tier 3" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_verified_token_cache(monkeypatch):
    """Tests that token verification is cached in-memory and subsequent calls avoid network hits."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.security import HTTPAuthorizationCredentials

    test_sub = uuid.uuid4()
    mock_get = AsyncMock(
        return_value=httpx.Response(
            200,
            json={"id": str(test_sub), "email": "cached_user@example.com", "user_metadata": {"role": "ADMIN"}},
        )
    )
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    mock_db = AsyncMock()
    user_record = User(
        id=test_sub,
        auth_user_id=test_sub,
        email="cached_user@example.com",
        full_name="Cached User",
        role="ADMIN",
        is_active=True,
    )
    res = MagicMock()
    res.scalar_one_or_none.return_value = user_record
    mock_db.execute = AsyncMock(return_value=res)

    token_str = f"test-cache-token-{uuid.uuid4()}"
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_str)

    # First call: hits network / Tier 1
    user1 = await get_current_user(credentials=creds, db=mock_db)
    assert user1.auth_user_id == test_sub
    assert mock_get.call_count == 1

    # Second call with the same token: hits cache, network call count remains 1
    user2 = await get_current_user(credentials=creds, db=mock_db)
    assert user2.auth_user_id == test_sub
    assert mock_get.call_count == 1


