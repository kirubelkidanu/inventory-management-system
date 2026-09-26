from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.api.routes.items import get_item_service
from app.core.config import settings
from app.main import app
from app.models.item import Item


class FakeCategoryStore:
    def __init__(self):
        self.store: dict[str, object] = {}
        # Seed with a valid category for testing
        self.valid_category_id = uuid4()
        self.store[str(self.valid_category_id)] = True


class FakeItemService:
    def __init__(self):
        self.store: dict[str, Item] = {}
        self.categories = FakeCategoryStore()

    async def list_items(self):
        return list(self.store.values())

    async def get_item(self, item_id):
        item = self.store.get(str(item_id))
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found.")
        return item

    async def create_item(self, payload):
        if any(item.item_code == payload.item_code for item in self.store.values()):
            raise HTTPException(status_code=409, detail="Item code already exists.")
        if str(payload.category_id) not in self.categories.store:
            raise HTTPException(status_code=400, detail="category_id references a non-existent category.")
        item = Item(
            id=uuid4(),
            item_code=payload.item_code,
            description=payload.description,
            category_id=payload.category_id,
            default_unit=payload.default_unit,
            is_active=payload.is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.store[str(item.id)] = item
        return item

    async def update_item(self, item_id, payload):
        item = await self.get_item(item_id)
        if payload.description is not None:
            item.description = payload.description
        if payload.category_id is not None and payload.category_id != item.category_id:
            if str(payload.category_id) not in self.categories.store:
                raise HTTPException(status_code=400, detail="category_id references a non-existent category.")
            item.category_id = payload.category_id
        if payload.default_unit is not None:
            item.default_unit = payload.default_unit
        if payload.is_active is not None:
            item.is_active = payload.is_active
        item.updated_at = datetime.now(timezone.utc)
        return item

    async def delete_item(self, item_id):
        item = await self.get_item(item_id)
        self.store.pop(str(item.id), None)


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
    return FakeItemService()


@pytest.mark.asyncio
async def test_item_routes_are_registered():
    assert app.url_path_for("list_items") == "/api/v1/items"
    assert app.url_path_for("get_item", item_id="123") == "/api/v1/items/123"


@pytest.mark.asyncio
async def test_item_routes_require_auth(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/items")
    app.dependency_overrides.clear()
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_item_routes_authorize_existing_roles(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="VIEWER")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/items",
            json={
                "item_code": "TEST-001",
                "description": "Test Item",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_item(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/items",
            json={
                "item_code": "ITEM-001",
                "description": "Test Item",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 201
    body = response.json()
    assert body["item_code"] == "ITEM-001"
    assert body["description"] == "Test Item"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_list_items(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/items", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_item(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/items",
            json={
                "item_code": "ITEM-GET",
                "description": "Get Item",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Kg",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        created = create_resp.json()
        response = await client.get(f"/api/v1/items/{created['id']}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["item_code"] == "ITEM-GET"


@pytest.mark.asyncio
async def test_update_item(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="INVENTORY_MANAGER")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/items",
            json={
                "item_code": "ITEM-UPDATE",
                "description": "Old Description",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        item_id = create_resp.json()["id"]
        response = await client.put(
            f"/api/v1/items/{item_id}",
            json={"description": "New Description", "default_unit": "M2"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["description"] == "New Description"
    assert response.json()["default_unit"] == "M2"


@pytest.mark.asyncio
async def test_delete_item(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/items",
            json={
                "item_code": "ITEM-DELETE",
                "description": "Delete Item",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        item_id = create_resp.json()["id"]
        response = await client.delete(f"/api/v1/items/{item_id}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_not_found_item(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    missing_id = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/items/{missing_id}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_category_reference(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    invalid_category_id = uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/items",
            json={
                "item_code": "ITEM-BAD-CAT",
                "description": "Bad Category Link",
                "category_id": str(invalid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_item_code_immutable(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/items",
            json={
                "item_code": "IMMUTABLE-001",
                "description": "Item with fixed code",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        item_id = create_resp.json()["id"]
        # Attempt to change item_code in PUT (should be ignored)
        response = await client.put(
            f"/api/v1/items/{item_id}",
            json={"item_code": "CHANGED-001", "description": "New description"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    # Verify item_code was not changed (field not in update schema)
    assert response.json()["item_code"] == "IMMUTABLE-001"
    assert response.json()["description"] == "New description"


@pytest.mark.asyncio
async def test_item_validation(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/items",
            json={"item_code": "", "description": "", "category_id": str(uuid4()), "default_unit": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 422
