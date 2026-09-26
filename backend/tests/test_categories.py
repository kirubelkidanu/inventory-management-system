from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.api.routes.categories import get_category_service
from app.core.config import settings
from app.main import app
from app.models.category import Category


class FakeCategoryService:
    def __init__(self):
        self.store: dict[str, Category] = {}

    async def list_categories(self):
        return list(self.store.values())

    async def get_category(self, category_id):
        category = self.store.get(str(category_id))
        if category is None:
            raise HTTPException(status_code=404, detail="Category not found.")
        return category

    async def create_category(self, payload):
        if any(item.code == payload.code for item in self.store.values()):
            raise HTTPException(status_code=409, detail="Category code already exists.")
        category = Category(
            id=uuid4(),
            code=payload.code,
            name=payload.name,
            description=payload.description,
            is_active=payload.is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.store[str(category.id)] = category
        return category

    async def update_category(self, category_id, payload):
        category = await self.get_category(category_id)
        if payload.code is not None and payload.code != category.code:
            if any(item.code == payload.code for item in self.store.values() if item.id != category.id):
                raise HTTPException(status_code=409, detail="Category code already exists.")
            category.code = payload.code
        if payload.name is not None:
            category.name = payload.name
        if payload.description is not None:
            category.description = payload.description
        if payload.is_active is not None:
            category.is_active = payload.is_active
        category.updated_at = datetime.now(timezone.utc)
        return category

    async def delete_category(self, category_id):
        category = await self.get_category(category_id)
        self.store.pop(str(category.id), None)


@pytest.fixture
def token_factory():
    def make_token(role: str = "ADMIN", user_id: str = "user-123") -> str:
        return jwt.encode(
            {
                "sub": user_id,
                "email": f"{user_id}@example.com",
                "role": role,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )

    return make_token


@pytest.fixture
def fake_service():
    return FakeCategoryService()


@pytest.mark.asyncio
async def test_category_routes_are_registered():
    assert app.url_path_for("list_categories") == "/api/v1/categories"
    assert app.url_path_for("get_category", category_id="123") == "/api/v1/categories/123"


@pytest.mark.asyncio
async def test_category_routes_require_auth(token_factory, fake_service):
    app.dependency_overrides[get_category_service] = lambda: fake_service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/categories")
    app.dependency_overrides.clear()
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_category_routes_authorize_existing_roles(token_factory, fake_service):
    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="VIEWER")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/categories",
            json={"code": "CAT-TEST", "name": "Test Category", "description": "Example"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_category(token_factory, fake_service):
    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/categories",
            json={"code": "CAT-ADMIN", "name": "Admin Category", "description": "Created via API"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "CAT-ADMIN"
    assert body["name"] == "Admin Category"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_list_categories(token_factory, fake_service):
    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/categories", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_category(token_factory, fake_service):
    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/categories",
            json={"code": "CAT-GET", "name": "Get Category", "description": "For lookup"},
            headers={"Authorization": f"Bearer {token}"},
        )
        created = create_resp.json()
        response = await client.get(f"/api/v1/categories/{created['id']}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["code"] == "CAT-GET"


@pytest.mark.asyncio
async def test_update_category(token_factory, fake_service):
    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="INVENTORY_MANAGER")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/categories",
            json={"code": "CAT-UPDATE", "name": "Old Name", "description": "Old"},
            headers={"Authorization": f"Bearer {token}"},
        )
        category_id = create_resp.json()["id"]
        response = await client.put(
            f"/api/v1/categories/{category_id}",
            json={"name": "New Name", "description": "Updated"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_category(token_factory, fake_service):
    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/categories",
            json={"code": "CAT-DELETE", "name": "Delete Category", "description": "To be removed"},
            headers={"Authorization": f"Bearer {token}"},
        )
        category_id = create_resp.json()["id"]
        response = await client.delete(f"/api/v1/categories/{category_id}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_not_found_category(token_factory, fake_service):
    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    missing_id = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/categories/{missing_id}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_category_validation(token_factory, fake_service):
    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/categories",
            json={"code": "", "name": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 422
