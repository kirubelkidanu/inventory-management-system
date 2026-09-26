import pytest
from httpx import AsyncClient

from app.core.database import get_db as canonical_get_db
from app.main import app
from app.security.auth import get_current_user


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_fastapi_app_imports():
    assert app is not None
    assert app.title == "Inventory Management System"


def test_auth_dependency_imports():
    assert get_current_user is not None


def test_database_dependency_is_canonical():
    from app import dependencies

    assert dependencies.get_db is canonical_get_db


@pytest.mark.asyncio
async def test_cors_headers_for_allowed_origin(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_unhandled_exception_masks_internal_traceback():
    # Register a temporary test route that raises an unhandled error
    @app.get("/api/v1/test-error-leak")
    async def route_that_fails():
        raise RuntimeError("Secret_DB_Password_Leak_12345")

    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        res = await client.get("/api/v1/test-error-leak")
        assert res.status_code == 500
        data = res.json()
        assert "Secret_DB_Password_Leak_12345" not in res.text
        assert "internal server error" in data["detail"].lower()