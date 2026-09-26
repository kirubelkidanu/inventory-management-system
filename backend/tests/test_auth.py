from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import settings
from app.main import app
from app.security.auth import AuthenticatedUser, get_current_user, require_roles


@pytest.fixture
def protected_app():
    api = FastAPI()

    @api.get("/protected")
    async def protected(user: AuthenticatedUser = Depends(get_current_user)):
        return {"user_id": user.user_id, "email": user.email, "role": user.role}

    @api.get("/role-protected")
    async def role_protected(
        user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER"))
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
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_invalid_bearer_format_fails(protected_app):
    async with AsyncClient(transport=ASGITransport(app=protected_app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": "Basic abc"})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_invalid_token_fails(protected_app):
    async with AsyncClient(transport=ASGITransport(app=protected_app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": "Bearer not-a-valid-token"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_valid_token_succeeds(protected_app):
    token = jwt.encode(
        {
            "sub": "user-123",
            "email": "user@example.com",
            "role": "ADMIN",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    async with AsyncClient(transport=ASGITransport(app=protected_app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-123", "email": "user@example.com", "role": "ADMIN"}


@pytest.mark.asyncio
async def test_expired_token_fails(protected_app):
    expired = jwt.encode(
        {
            "sub": "expired-user",
            "email": "expired@example.com",
            "role": "VIEWER",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    async with AsyncClient(transport=ASGITransport(app=protected_app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_role_check_fails_when_user_is_not_allowed(protected_app):
    token = jwt.encode(
        {
            "sub": "viewer-user",
            "email": "viewer@example.com",
            "role": "VIEWER",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    async with AsyncClient(transport=ASGITransport(app=protected_app), base_url="http://test") as client:
        response = await client.get("/role-protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_auth_token_success_for_demo_account():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@ims.local", "password": "password123"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@ims.local"
    assert data["user"]["role"] == "ADMIN"

    # Decode and verify the issued JWT
    decoded = jwt.decode(
        data["access_token"],
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        options={"verify_aud": False},
    )
    assert decoded["sub"] == str(data["user"]["id"])
    assert decoded["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_auth_token_unknown_account_fails():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/token",
            json={"email": "unknown@domain.com", "password": "password123"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_demo_login_all_roles_succeed():
    roles = ["ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER", "VIEWER"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for r in roles:
            response = await client.post(
                "/api/v1/auth/demo-login",
                json={"role": r},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["user"]["role"] == r
            assert "access_token" in data


@pytest.mark.asyncio
async def test_demo_login_invalid_role_fails():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/demo-login",
            json={"role": "SUPER_USER"},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_auth_me_with_valid_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Get token
        login_res = await client.post(
            "/api/v1/auth/demo-login",
            json={"role": "STORE_KEEPER"},
        )
        token = login_res.json()["access_token"]

        # 2. Call /me
        me_res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["role"] == "STORE_KEEPER"
        assert me_data["email"] == "storekeeper@ims.local"


@pytest.mark.asyncio
async def test_issued_token_authenticates_protected_endpoints():
    class DummyItemService:
        async def list_items(self):
            return []

    from app.api.routes.items import get_item_service
    app.dependency_overrides[get_item_service] = lambda: DummyItemService()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Obtain demo token
            login_res = await client.post(
                "/api/v1/auth/demo-login",
                json={"role": "ADMIN"},
            )
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]

            # 2. Access protected items route using the issued token
            res = await client.get(
                "/api/v1/items",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            assert res.json() == []
    finally:
        app.dependency_overrides.pop(get_item_service, None)


