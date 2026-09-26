from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.api.routes.warehouses import get_warehouse_service
from app.core.config import settings
from app.main import app
from app.models.warehouse import Warehouse


class FakeWarehouseService:
    def __init__(self):
        self.store: dict[str, Warehouse] = {}
        self.valid_project_ids = {uuid4(), uuid4()}

    async def list_warehouses(self):
        return list(self.store.values())

    async def get_warehouse(self, warehouse_id):
        warehouse = self.store.get(str(warehouse_id))
        if warehouse is None:
            raise HTTPException(status_code=404, detail="Warehouse not found.")
        return warehouse

    async def create_warehouse(self, payload):
        if any(item.code == payload.code for item in self.store.values()):
            raise HTTPException(status_code=409, detail="Warehouse code already exists.")
        if payload.default_project_id is not None and payload.default_project_id not in self.valid_project_ids:
            raise HTTPException(status_code=400, detail="default_project_id references a non-existent project.")
        warehouse = Warehouse(
            id=uuid4(),
            code=payload.code,
            name=payload.name,
            location=payload.location,
            default_project_id=payload.default_project_id,
            is_active=payload.is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.store[str(warehouse.id)] = warehouse
        return warehouse

    async def update_warehouse(self, warehouse_id, payload):
        warehouse = await self.get_warehouse(warehouse_id)
        if payload.code is not None and payload.code != warehouse.code:
            if any(item.code == payload.code for item in self.store.values() if item.id != warehouse.id):
                raise HTTPException(status_code=409, detail="Warehouse code already exists.")
            warehouse.code = payload.code
        if payload.name is not None:
            warehouse.name = payload.name
        if payload.location is not None:
            warehouse.location = payload.location
        if payload.default_project_id is not None and payload.default_project_id != warehouse.default_project_id:
            warehouse.default_project_id = payload.default_project_id
        if payload.is_active is not None:
            warehouse.is_active = payload.is_active
        warehouse.updated_at = datetime.now(timezone.utc)
        return warehouse

    async def delete_warehouse(self, warehouse_id):
        warehouse = await self.get_warehouse(warehouse_id)
        self.store.pop(str(warehouse.id), None)


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
    return FakeWarehouseService()


@pytest.mark.asyncio
async def test_warehouse_routes_are_registered():
    assert app.url_path_for("list_warehouses") == "/api/v1/warehouses"
    assert app.url_path_for("get_warehouse", warehouse_id="123") == "/api/v1/warehouses/123"


@pytest.mark.asyncio
async def test_warehouse_routes_require_auth(token_factory, fake_service):
    app.dependency_overrides[get_warehouse_service] = lambda: fake_service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/warehouses")
    app.dependency_overrides.clear()
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_warehouse_routes_authorize_existing_roles(token_factory, fake_service):
    app.dependency_overrides[get_warehouse_service] = lambda: fake_service
    token = token_factory(role="VIEWER")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/warehouses",
            json={"code": "WH-TEST", "name": "Test Warehouse", "location": "HQ"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_warehouse(token_factory, fake_service):
    app.dependency_overrides[get_warehouse_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/warehouses",
            json={"code": "WH-ADMIN", "name": "Admin Warehouse", "location": "Addis"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "WH-ADMIN"
    assert body["name"] == "Admin Warehouse"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_list_warehouses(token_factory, fake_service):
    app.dependency_overrides[get_warehouse_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/warehouses", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_warehouse(token_factory, fake_service):
    app.dependency_overrides[get_warehouse_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/warehouses",
            json={"code": "WH-GET", "name": "Get Warehouse", "location": "Lookup"},
            headers={"Authorization": f"Bearer {token}"},
        )
        created = create_resp.json()
        response = await client.get(f"/api/v1/warehouses/{created['id']}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["code"] == "WH-GET"


@pytest.mark.asyncio
async def test_update_warehouse(token_factory, fake_service):
    app.dependency_overrides[get_warehouse_service] = lambda: fake_service
    token = token_factory(role="INVENTORY_MANAGER")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/warehouses",
            json={"code": "WH-UPDATE", "name": "Old Warehouse", "location": "Old"},
            headers={"Authorization": f"Bearer {token}"},
        )
        warehouse_id = create_resp.json()["id"]
        response = await client.put(
            f"/api/v1/warehouses/{warehouse_id}",
            json={"name": "New Warehouse", "location": "Updated"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["name"] == "New Warehouse"


@pytest.mark.asyncio
async def test_delete_warehouse(token_factory, fake_service):
    app.dependency_overrides[get_warehouse_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/warehouses",
            json={"code": "WH-DELETE", "name": "Delete Warehouse", "location": "Remove"},
            headers={"Authorization": f"Bearer {token}"},
        )
        warehouse_id = create_resp.json()["id"]
        response = await client.delete(f"/api/v1/warehouses/{warehouse_id}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_not_found_warehouse(token_factory, fake_service):
    app.dependency_overrides[get_warehouse_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    missing_id = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/warehouses/{missing_id}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_project_reference(token_factory, fake_service):
    app.dependency_overrides[get_warehouse_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    invalid_project_id = uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/warehouses",
            json={"code": "WH-INVALID-PROJECT", "name": "Bad Project Link", "location": "HQ", "default_project_id": str(invalid_project_id)},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_warehouse_validation(token_factory, fake_service):
    app.dependency_overrides[get_warehouse_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/warehouses",
            json={"code": "", "name": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 422
