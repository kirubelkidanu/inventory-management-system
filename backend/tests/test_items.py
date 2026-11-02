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
from app.schemas.item import ItemBulkDeleteResult, ItemDeleteResult


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
        self.items_with_history: set[str] = set()

    async def list_items(self, include_inactive: bool = False):
        if include_inactive:
            return list(self.store.values())
        return [item for item in self.store.values() if item.is_active]

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

    async def delete_item(self, item_id, actor_user_id=None):
        item = await self.get_item(item_id)
        if str(item.id) in self.items_with_history:
            item.is_active = False
            return ItemDeleteResult(
                id=item.id,
                item_code=item.item_code,
                outcome="ARCHIVED",
                message=f"Item {item.item_code} has history and was archived.",
            )
        self.store.pop(str(item.id), None)
        return ItemDeleteResult(
            id=item.id,
            item_code=item.item_code,
            outcome="DELETED",
            message=f"Item {item.item_code} was permanently deleted.",
        )

    async def bulk_delete_items(self, item_ids, actor_user_id=None):
        deleted_count = 0
        archived_count = 0
        results = []
        for item_id in item_ids:
            item = self.store.get(str(item_id))
            if item is None:
                continue
            if str(item.id) in self.items_with_history:
                item.is_active = False
                archived_count += 1
                results.append(
                    ItemDeleteResult(
                        id=item.id,
                        item_code=item.item_code,
                        outcome="ARCHIVED",
                        message=f"Item {item.item_code} has history and was archived.",
                    )
                )
            else:
                self.store.pop(str(item.id), None)
                deleted_count += 1
                results.append(
                    ItemDeleteResult(
                        id=item.id,
                        item_code=item.item_code,
                        outcome="DELETED",
                        message=f"Item {item.item_code} was permanently deleted.",
                    )
                )
        return ItemBulkDeleteResult(
            deleted_count=deleted_count,
            archived_count=archived_count,
            results=results,
        )

    async def restore_item(self, item_id, actor_user_id=None):
        item = await self.get_item(item_id)
        item.is_active = True
        item.updated_at = datetime.now(timezone.utc)
        return item


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
async def test_create_item_unauthorized(fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/items")
    app.dependency_overrides.clear()
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_item_admin_success(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/items",
            json={
                "item_code": "ITEM-001",
                "description": "Admin Item",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 201
    assert response.json()["item_code"] == "ITEM-001"


@pytest.mark.asyncio
async def test_create_item_duplicate_code_conflict(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/items",
            json={
                "item_code": "DUPLICATE-001",
                "description": "First Item",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.post(
            "/api/v1/items",
            json={
                "item_code": "DUPLICATE-001",
                "description": "Second Item",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_items(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/items", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == []


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
                "default_unit": "Pcs",
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
    token = token_factory(role="ADMIN")
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
    assert response.status_code == 200
    data = response.json()
    assert data["outcome"] == "DELETED"
    assert data["item_code"] == "ITEM-DELETE"


@pytest.mark.asyncio
async def test_delete_item_with_history_archives_instead_of_delete(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/items",
            json={
                "item_code": "ITEM-USED",
                "description": "Used Item With History",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        item_id = create_resp.json()["id"]
        # Simulate that this item has history
        fake_service.items_with_history.add(item_id)

        response = await client.delete(f"/api/v1/items/{item_id}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["outcome"] == "ARCHIVED"
    assert data["item_code"] == "ITEM-USED"

    # Confirm item still exists in store but is inactive
    item = fake_service.store[item_id]
    assert item.is_active is False


@pytest.mark.asyncio
async def test_bulk_delete_items(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create 1 item with history, 2 without
        r1 = await client.post(
            "/api/v1/items",
            json={
                "item_code": "BULK-1",
                "description": "Unused 1",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        r2 = await client.post(
            "/api/v1/items",
            json={
                "item_code": "BULK-2",
                "description": "Used with history",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        r3 = await client.post(
            "/api/v1/items",
            json={
                "item_code": "BULK-3",
                "description": "Unused 2",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        id1 = r1.json()["id"]
        id2 = r2.json()["id"]
        id3 = r3.json()["id"]

        fake_service.items_with_history.add(id2)

        bulk_resp = await client.post(
            "/api/v1/items/bulk-delete",
            json={"item_ids": [id1, id2, id3]},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert bulk_resp.status_code == 200
    data = bulk_resp.json()
    assert data["deleted_count"] == 2
    assert data["archived_count"] == 1
    assert len(data["results"]) == 3

    results_map = {res["item_code"]: res["outcome"] for res in data["results"]}
    assert results_map["BULK-1"] == "DELETED"
    assert results_map["BULK-2"] == "ARCHIVED"
    assert results_map["BULK-3"] == "DELETED"


@pytest.mark.asyncio
async def test_restore_item(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/items",
            json={
                "item_code": "RESTORE-001",
                "description": "To be restored",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
                "is_active": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        item_id = create_resp.json()["id"]
        # Soft-archive it
        fake_service.store[item_id].is_active = False

        # Restore it
        patch_resp = await client.patch(
            f"/api/v1/items/{item_id}/restore",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is True
    assert fake_service.store[item_id].is_active is True


@pytest.mark.asyncio
async def test_include_inactive_items_toggle(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r_active = await client.post(
            "/api/v1/items",
            json={
                "item_code": "ACTIVE-01",
                "description": "Active item",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
                "is_active": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        r_inactive = await client.post(
            "/api/v1/items",
            json={
                "item_code": "INACTIVE-01",
                "description": "Inactive item",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
                "is_active": False,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # Default: include_inactive=False -> only ACTIVE-01
        res_default = await client.get("/api/v1/items", headers={"Authorization": f"Bearer {token}"})
        assert res_default.status_code == 200
        codes_default = [item["item_code"] for item in res_default.json()]
        assert "ACTIVE-01" in codes_default
        assert "INACTIVE-01" not in codes_default

        # With include_inactive=True -> both
        res_all = await client.get("/api/v1/items?include_inactive=true", headers={"Authorization": f"Bearer {token}"})
        assert res_all.status_code == 200
        codes_all = [item["item_code"] for item in res_all.json()]
        assert "ACTIVE-01" in codes_all
        assert "INACTIVE-01" in codes_all
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_and_bulk_delete_forbidden_for_non_admin(token_factory, fake_service):
    app.dependency_overrides[get_item_service] = lambda: fake_service
    admin_token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/items",
            json={
                "item_code": "AUTH-TEST",
                "description": "Auth Check Item",
                "category_id": str(fake_service.categories.valid_category_id),
                "default_unit": "Pcs",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        item_id = create_resp.json()["id"]

        for role in ["STORE_KEEPER", "INVENTORY_MANAGER", "VIEWER"]:
            role_token = token_factory(role=role)
            # Test single delete
            del_resp = await client.delete(
                f"/api/v1/items/{item_id}",
                headers={"Authorization": f"Bearer {role_token}"},
            )
            assert del_resp.status_code == 403

            # Test bulk delete
            bulk_resp = await client.post(
                "/api/v1/items/bulk-delete",
                json={"item_ids": [item_id]},
                headers={"Authorization": f"Bearer {role_token}"},
            )
            assert bulk_resp.status_code == 403
    app.dependency_overrides.clear()


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


@pytest.mark.asyncio
async def test_item_service_delete_unused_item_hard_deletes():
    from unittest.mock import AsyncMock, MagicMock
    from app.services.item import ItemService
    from app.models.inventory import InventoryBalance

    mock_session = AsyncMock()
    service = ItemService(mock_session)

    test_item = Item(
        id=uuid4(),
        item_code="UNUSED-ITEM",
        description="Unused Item",
        category_id=uuid4(),
        default_unit="Pcs",
        is_active=True,
    )
    zero_balance = InventoryBalance(
        id=uuid4(),
        warehouse_id=uuid4(),
        item_id=test_item.id,
        quantity_on_hand=0,
        quantity_reserved=0,
    )

    service.repository.get_by_id = AsyncMock(return_value=test_item)
    service.repository.check_item_usage = AsyncMock(return_value=(False, [zero_balance]))
    service.repository.delete_zero_balances = AsyncMock()
    service.repository.delete = AsyncMock()
    service.repository.create_audit_log = AsyncMock()
    service.repository.commit = AsyncMock()

    result = await service.delete_item(test_item.id, actor_user_id="user-admin")

    assert result.outcome == "DELETED"
    assert result.item_code == "UNUSED-ITEM"
    service.repository.delete_zero_balances.assert_awaited_once_with(test_item.id)
    service.repository.delete.assert_awaited_once_with(test_item)
    service.repository.create_audit_log.assert_awaited_once()
    audit_call = service.repository.create_audit_log.await_args
    assert audit_call.kwargs["action"] == "DELETE"
    assert audit_call.kwargs["entity_id"] == str(test_item.id)
    service.repository.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_item_service_delete_used_item_soft_archives():
    from unittest.mock import AsyncMock
    from app.services.item import ItemService
    from app.models.inventory import InventoryBalance

    mock_session = AsyncMock()
    service = ItemService(mock_session)

    test_item = Item(
        id=uuid4(),
        item_code="USED-ITEM",
        description="Used Item",
        category_id=uuid4(),
        default_unit="Pcs",
        is_active=True,
    )
    pos_balance = InventoryBalance(
        id=uuid4(),
        warehouse_id=uuid4(),
        item_id=test_item.id,
        quantity_on_hand=10,
        quantity_reserved=0,
    )

    service.repository.get_by_id = AsyncMock(return_value=test_item)
    service.repository.check_item_usage = AsyncMock(return_value=(True, [pos_balance]))
    service.repository.delete_zero_balances = AsyncMock()
    service.repository.delete = AsyncMock()
    service.repository.create_audit_log = AsyncMock()
    service.repository.commit = AsyncMock()

    result = await service.delete_item(test_item.id, actor_user_id="user-admin")

    assert result.outcome == "ARCHIVED"
    assert result.item_code == "USED-ITEM"
    assert test_item.is_active is False
    service.repository.delete.assert_not_called()
    service.repository.delete_zero_balances.assert_not_called()
    service.repository.create_audit_log.assert_awaited_once()
    audit_call = service.repository.create_audit_log.await_args
    assert audit_call.kwargs["action"] == "UPDATE"
    assert audit_call.kwargs["entity_id"] == str(test_item.id)
    service.repository.commit.assert_awaited_once()

