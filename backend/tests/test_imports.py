# backend/tests/test_imports.py
import csv
from datetime import datetime, timedelta, timezone
import io
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt
import openpyxl
import pytest

from app.api.routes.imports import get_import_service
from app.core.config import settings
from app.main import app
from app.models.category import Category
from app.models.import_ import ImportBatch, ImportError
from app.models.item import Item
from app.schemas.import_ import ImportBatchPreview, ImportBatchRead, ImportErrorRead
from app.services.import_ import ImportService, _to_uuid


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


def make_excel_bytes(sheets_data: dict[str, list[list]]) -> bytes:
    """Helper to create an in-memory .xlsx file bytes."""
    wb = openpyxl.Workbook()
    # remove default sheet
    default_sheet = wb.active
    first = True
    for sheet_name, rows in sheets_data.items():
        if first:
            ws = default_sheet
            ws.title = sheet_name
            first = False
        else:
            ws = wb.create_sheet(title=sheet_name)
        for r in rows:
            ws.append(r)

    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()


def make_csv_bytes(rows: list[list]) -> bytes:
    """Helper to create an in-memory .csv file bytes."""
    stream = io.StringIO()
    writer = csv.writer(stream)
    for r in rows:
        writer.writerow(r)
    return stream.getvalue().encode("utf-8")


class FakeImportService:
    def __init__(self):
        self.stage_calls = []
        self.commit_calls = []

    async def stage_item_master_file(self, user_id, file_name: str, file_bytes: bytes):
        self.stage_calls.append((user_id, file_name, file_bytes))
        batch_id = uuid4()
        return ImportBatch(
            id=batch_id,
            batch_number=f"IMP-ITEM-20260918-{uuid4().hex[:8].upper()}",
            import_type="ITEM_MASTER",
            file_name=file_name,
            file_size_bytes=len(file_bytes),
            total_rows=1,
            valid_rows=1,
            error_rows=0,
            status="VALIDATED",
            staged_data={"items": [{"item_code": "01-CM-00001", "description": "Portland Cement", "category_code": "CEMENT", "default_unit": "BAG"}]},
            created_by=_to_uuid(user_id),
            created_at=datetime.now(timezone.utc),
        )

    async def get_batch_preview(self, batch_id):
        batch = ImportBatch(
            id=batch_id,
            batch_number="IMP-ITEM-20260918-ABCD1234",
            import_type="ITEM_MASTER",
            file_name="items.xlsx",
            file_size_bytes=1024,
            total_rows=1,
            valid_rows=1,
            error_rows=0,
            status="VALIDATED",
            staged_data={"items": []},
            created_by=uuid4(),
            created_at=datetime.now(timezone.utc),
        )
        return ImportBatchPreview(
            batch=ImportBatchRead.model_validate(batch),
            errors=[],
            valid_items_sample=[],
        )

    async def commit_item_master_import(self, user_id, batch_id):
        self.commit_calls.append((user_id, batch_id))
        return {
            "message": "Item master import completed successfully.",
            "batch_id": batch_id,
            "batch_number": "IMP-ITEM-20260918-ABCD1234",
            "imported_count": 1,
        }


# ===========================================================================
# 1. Service Layer Tests: Staging & Parsing
# ===========================================================================


@pytest.mark.asyncio
async def test_stage_valid_excel_items():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    cat_id = uuid4()
    cement_cat = Category(
        id=cat_id, code="01-CM", name="CEMENT", is_active=True
    )
    service.repo.get_all_categories = AsyncMock(
        return_value={"01-CM": cement_cat, "CEMENT": cement_cat}
    )
    service.repo.get_existing_item_codes = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "CEMENT": [
            ["Inventory ID", "Description", "Major Category", "Unit Measurment"],
            ["01-CM-00001", "Portland Cement 42.5N", "CEMENT", "BAG"],
            ["01-CM-00002", "Rapid Hardening Cement", "01-CM", "BAG"],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)
    user_id = uuid4()

    batch = await service.stage_item_master_file(
        user_id=user_id, file_name="ItemMaster.xlsx", file_bytes=file_bytes
    )

    assert batch.status == "VALIDATED"
    assert batch.total_rows == 2
    assert batch.valid_rows == 2
    assert batch.error_rows == 0
    assert len(batch.staged_data["items"]) == 2
    assert batch.staged_data["items"][0]["item_code"] == "01-CM-00001"
    assert batch.staged_data["items"][0]["category_id"] == str(cat_id)
    service.repo.create_batch.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_stage_valid_csv_items():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    cat_id = uuid4()
    steel_cat = Category(
        id=cat_id, code="02-ST", name="STEEL", is_active=True
    )
    service.repo.get_all_categories = AsyncMock(
        return_value={"02-ST": steel_cat, "STEEL": steel_cat}
    )
    service.repo.get_existing_item_codes = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["Item Code", "Item Description", "Category", "Unit"],
        ["02-ST-00001", "Reinforcement Bar 12mm", "STEEL", "PCS"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_item_master_file(
        user_id=uuid4(), file_name="steel_items.csv", file_bytes=file_bytes
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 1
    assert batch.error_rows == 0
    assert batch.staged_data["items"][0]["item_code"] == "02-ST-00001"


@pytest.mark.asyncio
async def test_stage_catches_duplicate_item_codes_in_file():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    cat_id = uuid4()
    cat = Category(id=cat_id, code="01-CM", name="CEMENT", is_active=True)
    service.repo.get_all_categories = AsyncMock(return_value={"CEMENT": cat})
    service.repo.get_existing_item_codes = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "Sheet1": [
            ["Item Code", "Description", "Category", "Unit"],
            ["01-CM-00001", "Item A", "CEMENT", "BAG"],
            ["01-CM-00001", "Duplicate Item A", "CEMENT", "BAG"],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_item_master_file(
        user_id=uuid4(), file_name="items.xlsx", file_bytes=file_bytes
    )

    assert batch.status == "PARSED"
    assert batch.valid_rows == 1
    assert batch.error_rows == 1
    # Check that error was logged
    service.repo.create_errors.assert_called_once()
    errors = service.repo.create_errors.call_args[0][0]
    assert any(err.error_code == "DUPLICATE_CODE" for err in errors)


@pytest.mark.asyncio
async def test_stage_catches_existing_catalog_code():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    cat = Category(id=uuid4(), code="01-CM", name="CEMENT", is_active=True)
    service.repo.get_all_categories = AsyncMock(return_value={"CEMENT": cat})
    service.repo.get_existing_item_codes = AsyncMock(return_value={"01-CM-00001"})
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "Sheet1": [
            ["Item Code", "Description", "Category", "Unit"],
            ["01-CM-00001", "Already in DB", "CEMENT", "BAG"],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_item_master_file(
        user_id=uuid4(), file_name="items.xlsx", file_bytes=file_bytes
    )

    assert batch.valid_rows == 0
    assert batch.error_rows == 1
    service.repo.create_errors.assert_called_once()
    errors = service.repo.create_errors.call_args[0][0]
    assert errors[0].error_code == "DUPLICATE_CODE"
    assert "already exists in catalog" in errors[0].error_message


@pytest.mark.asyncio
async def test_stage_catches_missing_description_and_corrupt_draft_row():
    """Specific test for trailing row anomalies such as 07-PC-D0159."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    cat = Category(id=uuid4(), code="07-PC", name="PAINT AND CHEMICAL", is_active=True)
    service.repo.get_all_categories = AsyncMock(return_value={"PAINT AND CHEMICAL": cat})
    service.repo.get_existing_item_codes = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "PAINT AND CHEMICAL": [
            ["Item Code", "Description", "Category", "Unit"],
            ["07-PC-D0159", "", "PAINT AND CHEMICAL", "LITER"],  # corrupt draft row
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_item_master_file(
        user_id=uuid4(), file_name="paint.xlsx", file_bytes=file_bytes
    )

    assert batch.valid_rows == 0
    assert batch.error_rows == 1
    service.repo.create_errors.assert_called_once()
    errors = service.repo.create_errors.call_args[0][0]
    assert errors[0].error_code == "MISSING_DESCRIPTION"


@pytest.mark.asyncio
async def test_stage_catches_invalid_category():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    service.repo.get_all_categories = AsyncMock(return_value={})
    service.repo.get_existing_item_codes = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "Sheet1": [
            ["Item Code", "Description", "Category", "Unit"],
            ["UNKNOWN-01", "Some tool", "ASTRONOMY_TOOLS", "PCS"],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_item_master_file(
        user_id=uuid4(), file_name="tools.xlsx", file_bytes=file_bytes
    )

    assert batch.valid_rows == 0
    assert batch.error_rows == 1
    errors = service.repo.create_errors.call_args[0][0]
    assert errors[0].error_code == "INVALID_CATEGORY"


@pytest.mark.asyncio
async def test_stage_catches_missing_uom():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    cat = Category(id=uuid4(), code="02-ST", name="STEEL", is_active=True)
    service.repo.get_all_categories = AsyncMock(return_value={"STEEL": cat})
    service.repo.get_existing_item_codes = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    # Sheet with blank unit
    excel_data = {
        "STEEL": [
            ["Item Code", "Description", "Category", "Unit"],
            ["02-ST-00001", "Steel bar", "STEEL", ""],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_item_master_file(
        user_id=uuid4(), file_name="steel.xlsx", file_bytes=file_bytes
    )

    assert batch.valid_rows == 0
    assert batch.error_rows == 1
    errors = service.repo.create_errors.call_args[0][0]
    assert errors[0].error_code == "MISSING_UOM"


# ===========================================================================
# 2. Service Layer Tests: Commit Batch
# ===========================================================================


@pytest.mark.asyncio
async def test_commit_batch_success():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    batch_id = uuid4()
    cat_id = uuid4()
    batch = ImportBatch(
        id=batch_id,
        batch_number="IMP-ITEM-20260918-0001",
        import_type="ITEM_MASTER",
        file_name="items.xlsx",
        file_size_bytes=100,
        total_rows=1,
        valid_rows=1,
        error_rows=0,
        status="VALIDATED",
        staged_data={
            "items": [
                {
                    "item_code": "01-CM-00001",
                    "description": "Portland Cement",
                    "category_id": str(cat_id),
                    "default_unit": "BAG",
                }
            ]
        },
        created_by=uuid4(),
    )
    service.repo.get_batch_by_id = AsyncMock(return_value=batch)
    service.repo.get_existing_item_codes = AsyncMock(return_value=set())
    service.repo.bulk_create_items = AsyncMock()
    service.repo.update_batch = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    result = await service.commit_item_master_import(user_id=uuid4(), batch_id=batch_id)

    assert result["imported_count"] == 1
    assert batch.status == "COMPLETED"
    assert batch.completed_at is not None

    service.repo.bulk_create_items.assert_called_once()
    created_items = service.repo.bulk_create_items.call_args[0][0]
    assert len(created_items) == 1
    assert created_items[0].item_code == "01-CM-00001"

    service.repo.create_audit_log.assert_called_once()
    audit_kwargs = service.repo.create_audit_log.call_args.kwargs
    assert audit_kwargs["action"] == "IMPORT"
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_commit_already_completed_batch_fails():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    batch_id = uuid4()
    batch = ImportBatch(
        id=batch_id,
        batch_number="IMP-ITEM-20260918-0002",
        import_type="ITEM_MASTER",
        file_name="items.xlsx",
        file_size_bytes=100,
        status="COMPLETED",
        staged_data={"items": []},
        created_by=uuid4(),
    )
    service.repo.get_batch_by_id = AsyncMock(return_value=batch)

    with pytest.raises(HTTPException) as exc:
        await service.commit_item_master_import(user_id=uuid4(), batch_id=batch_id)
    assert exc.value.status_code == 400
    assert "already been committed" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_commit_batch_without_valid_items_fails():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    batch_id = uuid4()
    batch = ImportBatch(
        id=batch_id,
        batch_number="IMP-ITEM-20260918-0003",
        import_type="ITEM_MASTER",
        file_name="items.xlsx",
        file_size_bytes=100,
        status="PARSED",
        staged_data={"items": []},  # empty
        created_by=uuid4(),
    )
    service.repo.get_batch_by_id = AsyncMock(return_value=batch)

    with pytest.raises(HTTPException) as exc:
        await service.commit_item_master_import(user_id=uuid4(), batch_id=batch_id)
    assert exc.value.status_code == 400
    assert "no valid items" in exc.value.detail.lower()


# ===========================================================================
# 3. API Endpoints & RBAC Tests
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["ADMIN", "INVENTORY_MANAGER"])
async def test_api_upload_authorized_roles_succeed(token_factory, role):
    fake_service = FakeImportService()
    app.dependency_overrides[get_import_service] = lambda: fake_service
    token = token_factory(role=role)

    csv_data = b"Item Code,Description,Category,Unit\n01-CM-00001,Cement,CEMENT,BAG\n"
    files = {"file": ("items.csv", csv_data, "text/csv")}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/imports/items/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 201
    data = response.json()
    assert data["import_type"] == "ITEM_MASTER"
    assert data["status"] == "VALIDATED"


@pytest.mark.asyncio
async def test_api_upload_store_keeper_is_forbidden(token_factory):
    fake_service = FakeImportService()
    app.dependency_overrides[get_import_service] = lambda: fake_service
    token = token_factory(role="STORE_KEEPER")

    files = {"file": ("items.csv", b"dummy", "text/csv")}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/imports/items/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_upload_viewer_is_forbidden(token_factory):
    fake_service = FakeImportService()
    app.dependency_overrides[get_import_service] = lambda: fake_service
    token = token_factory(role="VIEWER")

    files = {"file": ("items.csv", b"dummy", "text/csv")}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/imports/items/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["ADMIN", "INVENTORY_MANAGER"])
async def test_api_commit_authorized_roles_succeed(token_factory, role):
    fake_service = FakeImportService()
    app.dependency_overrides[get_import_service] = lambda: fake_service
    token = token_factory(role=role)
    batch_id = uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/imports/batches/{batch_id}/commit",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["imported_count"] == 1
    assert "completed successfully" in data["message"].lower()


@pytest.mark.asyncio
async def test_api_commit_store_keeper_is_forbidden(token_factory):
    fake_service = FakeImportService()
    app.dependency_overrides[get_import_service] = lambda: fake_service
    token = token_factory(role="STORE_KEEPER")
    batch_id = uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/imports/batches/{batch_id}/commit",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_get_batch_preview_success(token_factory):
    fake_service = FakeImportService()
    app.dependency_overrides[get_import_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    batch_id = uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/v1/imports/batches/{batch_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert "batch" in data
    assert "errors" in data
    assert "valid_items_sample" in data
