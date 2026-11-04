from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.api.routes.categories import get_category_service
from app.core.config import settings
from app.main import app
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.category import CategoryService


class FakeCategoryService:
    def __init__(self):
        self.store: dict[str, Category] = {}
        self.audit_logs: list[dict] = []

    async def list_categories(self, include_archived: bool = False, search: str | None = None):
        cats = list(self.store.values())
        if not include_archived:
            cats = [c for c in cats if c.is_active]
        if search:
            s = search.strip().upper()
            cats = [c for c in cats if s in c.code.upper() or s in c.name.upper()]
        for c in cats:
            if not hasattr(c, "item_count"):
                c.item_count = getattr(c, "_item_count", 0)
        return cats

    async def get_category(self, category_id):
        category = self.store.get(str(category_id))
        if category is None:
            raise HTTPException(status_code=404, detail="Category not found.")
        if not hasattr(category, "item_count"):
            category.item_count = getattr(category, "_item_count", 0)
        return category

    async def create_category(self, payload, user_id=None):
        clean_code = payload.code.strip().upper()
        if any(item.code == clean_code for item in self.store.values()):
            raise HTTPException(status_code=409, detail=f"Category code '{clean_code}' already exists.")
        category = Category(
            id=uuid4(),
            code=clean_code,
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
            is_active=payload.is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        category._item_count = 0
        category.item_count = 0
        self.store[str(category.id)] = category
        self.audit_logs.append({
            "action": "CREATE",
            "entity_type": "category",
            "entity_id": str(category.id),
            "actor_user_id": user_id,
        })
        return category

    async def update_category(self, category_id, payload, user_id=None):
        category = await self.get_category(category_id)
        if payload.code is not None and payload.code.strip().upper() != category.code:
            clean_code = payload.code.strip().upper()
            if any(item.code == clean_code for item in self.store.values() if item.id != category.id):
                raise HTTPException(status_code=409, detail=f"Category code '{clean_code}' already exists.")
            category.code = clean_code
        if payload.name is not None:
            category.name = payload.name.strip()
        if payload.description is not None:
            category.description = payload.description.strip() if payload.description else None
        if payload.is_active is not None:
            category.is_active = payload.is_active
        category.updated_at = datetime.now(timezone.utc)
        self.audit_logs.append({
            "action": "UPDATE",
            "entity_type": "category",
            "entity_id": str(category.id),
            "actor_user_id": user_id,
        })
        return category

    async def toggle_status(self, category_id, is_active=None, user_id=None):
        category = await self.get_category(category_id)
        new_status = not category.is_active if is_active is None else is_active
        return await self.update_category(
            category_id,
            CategoryUpdate(is_active=new_status),
            user_id=user_id,
        )

    async def delete_category(self, category_id, user_id=None):
        category = await self.get_category(category_id)
        category.is_active = False
        self.audit_logs.append({
            "action": "UPDATE",
            "entity_type": "category",
            "entity_id": str(category.id),
            "actor_user_id": user_id,
        })


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
async def test_category_routes_require_auth(fake_service):
    app.dependency_overrides[get_category_service] = lambda: fake_service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/categories")
    app.dependency_overrides.clear()
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_non_admin_forbidden_on_post_and_put(token_factory, fake_service):
    """Test non-admin user (e.g. INVENTORY_MANAGER, VIEWER) receives HTTP 403 Forbidden on write operations."""
    app.dependency_overrides[get_category_service] = lambda: fake_service
    for role in ["VIEWER", "STORE_KEEPER", "INVENTORY_MANAGER"]:
        token = token_factory(role=role)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            post_resp = await client.post(
                "/api/v1/categories",
                json={"code": "19", "name": "Tools", "description": "Hand Tools"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert post_resp.status_code == 403

            put_resp = await client.put(
                f"/api/v1/categories/{uuid4()}",
                json={"name": "Updated Tools"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert put_resp.status_code == 403

            patch_resp = await client.patch(
                f"/api/v1/categories/{uuid4()}/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert patch_resp.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_category_success_and_audit_log(token_factory, fake_service):
    """Test POST /api/v1/categories creates category and audit log entry with action='CREATE'."""
    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="ADMIN", user_id="admin-999")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/categories",
            json={"code": "15", "name": "STATIONERY", "description": "Office paper and pens"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "15"
    assert body["name"] == "STATIONERY"
    assert body["is_active"] is True
    assert body["item_count"] == 0

    # Verify audit log
    assert len(fake_service.audit_logs) == 1
    assert fake_service.audit_logs[0]["action"] == "CREATE"
    assert fake_service.audit_logs[0]["entity_type"] == "category"


@pytest.mark.asyncio
async def test_create_category_duplicate_code_returns_409(token_factory, fake_service):
    """Test POST /api/v1/categories with duplicate code returns HTTP 409 Conflict."""
    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/api/v1/categories",
            json={"code": "17", "name": "CLEAN"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 201

        duplicate = await client.post(
            "/api/v1/categories",
            json={"code": "17", "name": "Cleaning Materials"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert duplicate.status_code == 409
        assert "already exists" in duplicate.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_categories_with_item_counts(token_factory, fake_service):
    """Test GET /api/v1/categories returns categories with active item counts and filters."""
    cat1 = Category(id=uuid4(), code="01", name="CEMENT", is_active=True)
    cat1._item_count = 40
    cat2 = Category(id=uuid4(), code="02", name="STEEL", is_active=False)
    cat2._item_count = 569
    fake_service.store[str(cat1.id)] = cat1
    fake_service.store[str(cat2.id)] = cat2

    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="VIEWER")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Default: only active
        res_active = await client.get("/api/v1/categories", headers={"Authorization": f"Bearer {token}"})
        assert res_active.status_code == 200
        data_active = res_active.json()
        assert len(data_active) == 1
        assert data_active[0]["code"] == "01"
        assert data_active[0]["item_count"] == 40

        # include_archived=true
        res_all = await client.get("/api/v1/categories?include_archived=true", headers={"Authorization": f"Bearer {token}"})
        assert res_all.status_code == 200
        data_all = res_all.json()
        assert len(data_all) == 2

        # search filter
        res_search = await client.get("/api/v1/categories?include_archived=true&search=STEEL", headers={"Authorization": f"Bearer {token}"})
        assert res_search.status_code == 200
        assert len(res_search.json()) == 1
        assert res_search.json()[0]["name"] == "STEEL"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_category_and_audit_log(token_factory, fake_service):
    """Test PUT /api/v1/categories/{id} updates category and records audit entry with action='UPDATE'."""
    cat = Category(id=uuid4(), code="16", name="HOUSEHOLD", description="Old description", is_active=True)
    fake_service.store[str(cat.id)] = cat

    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            f"/api/v1/categories/{cat.id}",
            json={"name": "HOUSEHOLD GOODS", "description": "Appliances and supplies"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "HOUSEHOLD GOODS"
    assert body["description"] == "Appliances and supplies"

    # Verify audit log
    assert any(log["action"] == "UPDATE" and log["entity_id"] == str(cat.id) for log in fake_service.audit_logs)


@pytest.mark.asyncio
async def test_patch_category_status_toggle(token_factory, fake_service):
    """Test PATCH /api/v1/categories/{id}/status toggles is_active flag."""
    cat = Category(id=uuid4(), code="18", name="COMPUTER & IT", is_active=True)
    fake_service.store[str(cat.id)] = cat

    app.dependency_overrides[get_category_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Toggle to inactive
        resp1 = await client.patch(
            f"/api/v1/categories/{cat.id}/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 200
        assert resp1.json()["is_active"] is False

        # Toggle back to active
        resp2 = await client.patch(
            f"/api/v1/categories/{cat.id}/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["is_active"] is True

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_service_create_and_audit_with_mock_db():
    """Unit test CategoryService with mock session asserting audit logging and conflict handling."""
    mock_session = AsyncMock()
    service = CategoryService(mock_session)

    service.repository.get_by_code = AsyncMock(return_value=None)
    service.repository.create = AsyncMock(side_effect=lambda cat: cat)
    service.repository.create_audit_log = AsyncMock()

    payload = CategoryCreate(code="15", name="STATIONERY", description="Office")
    cat = await service.create_category(payload, user_id=uuid4())

    assert cat.code == "15"
    assert cat.name == "STATIONERY"
    service.repository.create_audit_log.assert_called_once()
    assert service.repository.create_audit_log.call_args[1]["action"] == "CREATE"
