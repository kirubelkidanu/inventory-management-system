# backend/tests/test_imports.py
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
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
from app.models.warehouse import Warehouse
from app.models.transaction import Transaction
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
    assert errors[0].error_code == "ALREADY_EXISTS"
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
async def test_stage_skips_corrupt_draft_row_with_empty_description_and_unit():
    """Confirms empty draft rows (like 07-PC-D0159 in docs/PROJECT_SPEC.md Note 4) are dropped without errors."""
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
            ["07-PC-00001", "Red Oxide Primer", "PAINT AND CHEMICAL", "LTR"],
            ["07-PC-D0159", "", "PAINT AND CHEMICAL", ""],  # corrupt draft row with no desc & no uom
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_item_master_file(
        user_id=uuid4(), file_name="paint.xlsx", file_bytes=file_bytes
    )

    assert batch.valid_rows == 1
    assert batch.error_rows == 0
    assert len(batch.staged_data["items"]) == 1
    assert batch.staged_data["items"][0]["item_code"] == "07-PC-00001"


@pytest.mark.asyncio
async def test_stage_auto_defaults_steel_uom_to_pcs():
    """Verifies that all items in sheet STEEL or 02-ST-* default blank UOM to 'PCS' (PROJECT_SPEC.md Note 1)."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    steel_cat = Category(id=uuid4(), code="02-ST", name="STEEL", is_active=True)
    service.repo.get_all_categories = AsyncMock(return_value={"STEEL": steel_cat, "02-ST": steel_cat})
    service.repo.get_existing_item_codes = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "STEEL": [
            ["Item Code", "Description", "Category", "Unit"],
            ["02-ST-00001", "Reinforcement Bar 12mm High Yield", "STEEL", ""],
            ["02-ST-00002", "Reinforcement Bar 16mm High Yield", "STEEL", None],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_item_master_file(
        user_id=uuid4(), file_name="steel.xlsx", file_bytes=file_bytes
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 2
    assert batch.error_rows == 0
    assert batch.staged_data["items"][0]["default_unit"] == "PCS"
    assert batch.staged_data["items"][1]["default_unit"] == "PCS"


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

    cat = Category(id=uuid4(), code="01-CM", name="CEMENT", is_active=True)
    service.repo.get_all_categories = AsyncMock(return_value={"CEMENT": cat})
    service.repo.get_existing_item_codes = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    # Sheet with blank unit for non-steel item
    excel_data = {
        "CEMENT": [
            ["Item Code", "Description", "Category", "Unit"],
            ["01-CM-00001", "Portland Cement", "CEMENT", ""],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_item_master_file(
        user_id=uuid4(), file_name="cement.xlsx", file_bytes=file_bytes
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


@pytest.mark.asyncio
async def test_commit_batch_skips_existing_codes_idempotently():
    """Confirms commit filters out existing codes without failing and inserts only genuinely new items."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    batch_id = uuid4()
    cat_id = uuid4()
    batch = ImportBatch(
        id=batch_id,
        batch_number="IMP-ITEM-20260918-0004",
        import_type="ITEM_MASTER",
        file_name="items.xlsx",
        file_size_bytes=100,
        total_rows=2,
        valid_rows=2,
        error_rows=0,
        status="PARSED",
        staged_data={
            "items": [
                {
                    "item_code": "01-CM-00001",
                    "description": "Portland Cement (Already in DB)",
                    "category_id": str(cat_id),
                    "default_unit": "BAG",
                },
                {
                    "item_code": "01-CM-00002",
                    "description": "Rapid Hardening Cement (New)",
                    "category_id": str(cat_id),
                    "default_unit": "BAG",
                },
            ]
        },
        created_by=uuid4(),
    )
    service.repo.get_batch_by_id = AsyncMock(return_value=batch)
    # Simulate 01-CM-00001 already in database
    service.repo.get_existing_item_codes = AsyncMock(return_value={"01-CM-00001"})
    service.repo.bulk_create_items = AsyncMock()
    service.repo.update_batch = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    result = await service.commit_item_master_import(user_id=uuid4(), batch_id=batch_id)

    assert result["imported_count"] == 1
    assert "1 new items" in result["message"]
    assert "1 existing items skipped" in result["message"]
    assert batch.status == "COMPLETED"

    # Verify bulk_create_items was called only with 01-CM-00002
    service.repo.bulk_create_items.assert_called_once()
    created_items = service.repo.bulk_create_items.call_args[0][0]
    assert len(created_items) == 1
    assert created_items[0].item_code == "01-CM-00002"
    mock_session.commit.assert_called_once()


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


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/imports/items/stage", "/api/v1/imports/items/stage/"])
async def test_api_stage_items_success_with_and_without_trailing_slash(token_factory, path):
    fake_service = FakeImportService()
    app.dependency_overrides[get_import_service] = lambda: fake_service
    token = token_factory(role="ADMIN")

    csv_data = b"inventory id,description,category,unit measurment\n01-CM-00001,Cement,CEMENT,BAG\n"
    files = {"file": ("items.csv", csv_data, "text/csv")}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            path,
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert "batch" in data
    assert "errors" in data
    assert "valid_items_sample" in data


@pytest.mark.asyncio
@pytest.mark.parametrize("path_pattern", [
    "/api/v1/imports/items/{batch_id}/commit",
    "/api/v1/imports/items/{batch_id}/commit/",
    "/api/v1/imports/batches/{batch_id}/commit",
    "/api/v1/imports/batches/{batch_id}/commit/",
])
async def test_api_commit_items_all_path_aliases(token_factory, path_pattern):
    fake_service = FakeImportService()
    app.dependency_overrides[get_import_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    batch_id = uuid4()
    path = path_pattern.format(batch_id=batch_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            path,
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["imported_count"] == 1
    assert "completed successfully" in data["message"].lower()




# ==============================================================================
# Robust Opening Balance / Initial Stock Excel Parser Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_stage_initial_stock_with_title_rows_above_header():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    wh = Warehouse(id=wh_id, code="KL-WH-001", name="Kality Store", is_active=True)
    item1 = Item(
        id=uuid4(),
        item_code="01-CM-00001",
        description="Portland Cement 42.5N",
        default_unit="BAG",
        is_active=True,
    )
    item2 = Item(
        id=uuid4(),
        item_code="02-ST-00001",
        description="Reinforcement Steel 12mm",
        default_unit="PCS",
        is_active=True,
    )

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_warehouses_by_codes = AsyncMock(return_value={"KL-WH-001": wh})
    service.repo.get_items_by_codes = AsyncMock(
        return_value={"01-CM-00001": item1, "02-ST-00001": item2}
    )
    service.repo.get_projects_by_codes = AsyncMock(return_value={})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    # Title rows 1-4, real header on row 5, data on rows 6-7, summary on rows 8-9
    excel_data = {
        "Sheet1": [
            ["KALITY PROJECT 2 - OPENING INVENTORY REPORT", "", "", ""],
            ["Generated Date: 2026-10-01", "", "", ""],
            ["Target Warehouse: KL-WH-001", "", "", ""],
            ["", "", "", ""],
            ["Inventory ID", "Quantity", "Unit Measurement", "Unit Price"],
            ["01-CM-00001", 500, "BAG", 2113],
            ["02-ST-00001", 100, "PCS", 450],
            ["Total", 600, "", 1056500],
            ["Approved by: Project Manager", "", "", ""],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="kality_opening.xlsx",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 2
    assert batch.error_rows == 0
    assert len(batch.staged_data["rows"]) == 2
    assert batch.staged_data["rows"][0]["item_code"] == "01-CM-00001"
    assert batch.staged_data["rows"][0]["quantity"] == "500"
    assert batch.staged_data["rows"][1]["item_code"] == "02-ST-00001"
    assert batch.staged_data["rows"][1]["quantity"] == "100"


@pytest.mark.asyncio
async def test_stage_initial_stock_non_first_sheet():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    wh = Warehouse(id=wh_id, code="KL-WH-001", name="Kality Store", is_active=True)
    item = Item(
        id=uuid4(),
        item_code="01-CM-00001",
        description="Portland Cement",
        default_unit="BAG",
        is_active=True,
    )

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_warehouses_by_codes = AsyncMock(return_value={"KL-WH-001": wh})
    service.repo.get_items_by_codes = AsyncMock(return_value={"01-CM-00001": item})
    service.repo.get_projects_by_codes = AsyncMock(return_value={})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    # Cover sheet has notes, second sheet has actual stock data
    excel_data = {
        "Cover": [
            ["Instructions & Metadata", ""],
            ["Prepared By", "Kirubel"],
            ["Remarks", "Do not modify column orders"],
        ],
        "StockData": [
            ["Item Code", "Qty", "Unit", "Price"],
            ["01-CM-00001", 250, "BAG", 1200],
        ],
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="multisheet_stock.xlsx",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 1
    assert batch.error_rows == 0
    assert batch.staged_data["rows"][0]["item_code"] == "01-CM-00001"
    assert batch.staged_data["rows"][0]["quantity"] == "250"


@pytest.mark.asyncio
async def test_stage_initial_stock_4_column_valid_and_error_rows():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    wh = Warehouse(id=wh_id, code="KL-WH-001", name="Kality Store", is_active=True)
    item1 = Item(
        id=uuid4(),
        item_code="01-CM-00001",
        description="Cement 42.5N",
        default_unit="BAG",
        is_active=True,
    )

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_warehouses_by_codes = AsyncMock(return_value={"KL-WH-001": wh})
    service.repo.get_items_by_codes = AsyncMock(return_value={"01-CM-00001": item1})
    service.repo.get_projects_by_codes = AsyncMock(return_value={})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "Sheet1": [
            ["inventory id", "quantity", "unit measurment", "unit price"],
            ["01-CM-00001", 410, "BAG", 2113],
            ["INVALID-ITEM-999", 50, "BAG", 100],
            ["01-CM-00001", -5, "BAG", 2113],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="kality p2 begi (2).xlsx",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.valid_rows == 1
    assert batch.error_rows == 2
    assert len(batch.staged_data["rows"]) == 1
    assert batch.staged_data["rows"][0]["item_code"] == "01-CM-00001"

    service.repo.create_errors.assert_called_once()
    logged_errors = service.repo.create_errors.call_args[0][0]
    error_codes = [err.error_code for err in logged_errors]
    assert "INVALID_ITEM" in error_codes
    assert "INVALID_QUANTITY" in error_codes


@pytest.mark.asyncio
async def test_stage_initial_stock_headerless_4_column_format():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    wh = Warehouse(id=wh_id, code="KL-WH-001", name="Kality Store", is_active=True)
    item1 = Item(
        id=uuid4(),
        item_code="01-CM-00001",
        description="Cement 42.5N",
        default_unit="BAG",
        is_active=True,
    )
    item2 = Item(
        id=uuid4(),
        item_code="02-ST-00001",
        description="Steel Rebar 12mm",
        default_unit="PCS",
        is_active=True,
    )

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_warehouses_by_codes = AsyncMock(return_value={"KL-WH-001": wh})
    service.repo.get_items_by_codes = AsyncMock(
        return_value={"01-CM-00001": item1, "02-ST-00001": item2}
    )
    service.repo.get_projects_by_codes = AsyncMock(return_value={})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    # Raw 4-column data with no header row at all (like kality p2 begi.xlsx)
    excel_data = {
        "Sheet1": [
            ["01-CM-00001", 410, "BAG", 2113],
            ["02-ST-00001", 1755, "PCS", 771.3],
            ["Total", 2165, "", ""],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="kality p2 begi.xlsx",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 2
    assert batch.error_rows == 0
    assert len(batch.staged_data["rows"]) == 2
    assert batch.staged_data["rows"][0]["item_code"] == "01-CM-00001"
    assert batch.staged_data["rows"][0]["quantity"] == "410"
    assert batch.staged_data["rows"][1]["item_code"] == "02-ST-00001"
    assert batch.staged_data["rows"][1]["quantity"] == "1755"


@pytest.mark.asyncio
async def test_initial_stock_commit_audit_log_actions_satisfy_check_constraint():
    """Verifies that initial stock import commit writes action='IMPORT' conforming to audit_logs_action_check."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    batch_id = uuid4()
    user_id = uuid4()
    wh_id = uuid4()
    item_id = uuid4()

    batch = ImportBatch(
        id=batch_id,
        batch_number="IMP-STOCK-20261103-AUDIT01",
        import_type="INITIAL_STOCK",
        file_name="stock_audit.xlsx",
        file_size_bytes=2048,
        total_rows=1,
        valid_rows=1,
        error_rows=0,
        status="VALIDATED",
        staged_data={
            "rows": [
                {
                    "row_number": 1,
                    "item_id": str(item_id),
                    "warehouse_id": str(wh_id),
                    "quantity": 50.0,
                    "unit": "PCS",
                    "unit_price": 200.0,
                    "status": "VALID",
                }
            ]
        },
        created_by=user_id,
        created_at=datetime.now(timezone.utc),
    )

    service.repo.get_batch_by_id = AsyncMock(return_value=batch)
    service.repo.update_batch = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    mock_tx = Transaction(
        id=uuid4(),
        transaction_number="ADJ-20261103-AUDIT01",
        transaction_type="ADJUSTMENT",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=wh_id,
        adjustment_reason="Opening Balance",
        external_reference="OPENING_BALANCE",
        created_by=user_id,
    )
    service.tx_service.create_and_post_opening_balance = AsyncMock(return_value=mock_tx)

    result = await service.commit_initial_stock_import(user_id=user_id, batch_id=batch_id)

    assert result["batch_id"] == batch_id
    assert batch.status == "COMPLETED"

    # Verify batch audit log satisfies audit_logs_action_check
    service.repo.create_audit_log.assert_called_once()
    audit_call = service.repo.create_audit_log.call_args[1]
    valid_actions = {"CREATE", "UPDATE", "POST", "CANCEL", "CORRECT", "IMPORT", "DELETE"}
    assert audit_call["action"] == "IMPORT"
    assert audit_call["action"] in valid_actions
    assert audit_call["entity_type"] == "import_batch"
    assert audit_call["entity_id"] == str(batch.id)
    assert audit_call["actor_user_id"] == user_id



@pytest.mark.asyncio
async def test_stage_initial_stock_uom_case_insensitive_match():
    """Verifies that UOM matching is case-insensitive ('kg' matches 'KG')."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(
        id=item_id,
        item_code="02-ST-00001",
        description="Steel Rebar",
        default_unit="KG",
        is_active=True,
    )

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"02-ST-00001": item})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["02-ST-00001", "50", "kg", "75.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="uom_case.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 1
    assert batch.error_rows == 0
    staged_row = batch.staged_data["rows"][0]
    assert staged_row["unit"] == "KG"


@pytest.mark.asyncio
async def test_stage_initial_stock_uom_synonyms_mapping():
    """Verifies that canonical UOM synonyms map correctly ('ltr' -> 'Liter', 'pcs' -> 'Pcs', etc.)."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item_paint = Item(id=uuid4(), item_code="07-PC-00001", description="Paint", default_unit="Liter", is_active=True)
    item_bolts = Item(id=uuid4(), item_code="05-HW-00001", description="Bolts", default_unit="Pcs", is_active=True)
    item_tiles = Item(id=uuid4(), item_code="04-TL-00001", description="Ceramic Tiles", default_unit="M2", is_active=True)
    item_cement = Item(id=uuid4(), item_code="01-CM-00001", description="Cement", default_unit="BAG", is_active=True)
    item_grain = Item(id=uuid4(), item_code="09-AG-00001", description="Bulk Lime", default_unit="Qtl", is_active=True)

    items_map = {
        "07-PC-00001": item_paint,
        "05-HW-00001": item_bolts,
        "04-TL-00001": item_tiles,
        "01-CM-00001": item_cement,
        "09-AG-00001": item_grain,
    }

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value=items_map)
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["07-PC-00001", "20", "ltr", "120.00"],
        ["05-HW-00001", "100", "pieces", "5.50"],
        ["04-TL-00001", "45", "sqm", "350.00"],
        ["01-CM-00001", "80", "bags", "550.00"],
        ["09-AG-00001", "10", "quintal", "1800.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="uom_synonyms.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 5
    assert batch.error_rows == 0
    units_by_sku = {r["item_code"]: r["unit"] for r in batch.staged_data["rows"]}
    assert units_by_sku["07-PC-00001"] == "Liter"
    assert units_by_sku["05-HW-00001"] == "Pcs"
    assert units_by_sku["04-TL-00001"] == "M2"
    assert units_by_sku["01-CM-00001"] == "BAG"
    assert units_by_sku["09-AG-00001"] == "Qtl"


@pytest.mark.asyncio
async def test_stage_initial_stock_blank_uom_falls_back_to_default_unit():
    """Verifies that blank/whitespace UOM defaults safely to item.default_unit."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(id=item_id, item_code="01-CM-00001", description="Cement", default_unit="BAG", is_active=True)

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"01-CM-00001": item})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["01-CM-00001", "150", "", "550.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="blank_uom.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 1
    assert batch.staged_data["rows"][0]["unit"] == "BAG"


@pytest.mark.asyncio
async def test_stage_initial_stock_dimensional_mismatch_logs_invalid_uom():
    """Verifies that true dimensional conflict ('KG' vs 'Pkt') logs INVALID_UOM error."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(id=item_id, item_code="05-HW-00002", description="Small Screws", default_unit="Pkt", is_active=True)

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"05-HW-00002": item})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["05-HW-00002", "10", "KG", "80.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="mismatch_uom.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.valid_rows == 0
    assert batch.error_rows == 1
    logged_errors = service.repo.create_errors.call_args[0][0]
    assert any(err.error_code == "INVALID_UOM" for err in logged_errors)


@pytest.mark.asyncio
async def test_stage_initial_stock_merges_duplicate_skus_and_calculates_weighted_price():
    """
    Verifies that multiple rows with the same SKU merge into a single line with
    summed quantity and weighted average price, satisfying ADR-006.
    """
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()
    wh = Warehouse(id=wh_id, code="KZ-WH-001", name="Kazanchis Store", is_active=True)
    item = Item(id=item_id, item_code="01-CM-00001", description="Cement 42.5N", default_unit="BAG", is_active=True)

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"01-CM-00001": item})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()
    service.repo.get_batch_by_id = AsyncMock()
    service.repo.update_batch = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    # Row 2: 10 BAG @ 100 ETB
    # Row 3: 20 BAG @ 250 ETB
    # Weighted average price: (10*100 + 20*250) / 30 = 6000 / 30 = 200.0000
    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["01-CM-00001", "10", "BAG", "100.00"],
        ["01-CM-00001", "20", "BAG", "250.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=user_id,
        file_name="merge_skus.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 1  # 2 rows aggregated into 1
    assert batch.error_rows == 0

    staged_row = batch.staged_data["rows"][0]
    assert staged_row["item_code"] == "01-CM-00001"
    assert Decimal(staged_row["quantity"]) == Decimal("30")
    assert Decimal(staged_row["unit_price"]) == Decimal("200.0000")
    assert Decimal(staged_row["total_price"]) == Decimal("6000.0000")
    assert staged_row["is_merged"] is True
    assert staged_row["merged_count"] == 2
    assert staged_row["merged_rows"] == [1, 2]
    assert "Merged 2 rows" in staged_row["merge_note"]
    assert "30" in staged_row["merge_note"]

    # Now verify commit routes with exactly 1 line satisfying ADR-006 UNIQUE(transaction_id, item_id)
    service.repo.get_batch_by_id = AsyncMock(return_value=batch)
    mock_tx = Transaction(
        id=uuid4(),
        transaction_number="ADJ-20261103-MERGE01",
        transaction_type="ADJUSTMENT",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=wh_id,
        created_by=user_id,
    )
    service.tx_service.create_and_post_opening_balance = AsyncMock(return_value=mock_tx)

    result = await service.commit_initial_stock_import(user_id=user_id, batch_id=batch.id)
    assert result["batch_id"] == batch.id

    service.tx_service.create_and_post_opening_balance.assert_awaited_once()
    ob_call = service.tx_service.create_and_post_opening_balance.await_args[1]["payload"]
    assert len(ob_call.lines) == 1
    assert ob_call.lines[0].item_id == item_id
    assert ob_call.lines[0].quantity == Decimal("30")
    assert ob_call.lines[0].unit_price == Decimal("200.0000")



@pytest.mark.asyncio
async def test_stage_initial_stock_sku_spaces_around_hyphens():
    """Verifies that SKU code with spaces around hyphens ('11-OT -00106') resolves to canonical '11-OT-00106'."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(
        id=item_id,
        item_code="11-OT-00106",
        description="Office Tool",
        default_unit="PCS",
        is_active=True,
    )

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"11-OT-00106": item})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["11-OT -00106", "15", "PCS", "250.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="sku_spaces_around_hyphen.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 1
    assert batch.error_rows == 0
    staged_row = batch.staged_data["rows"][0]
    assert staged_row["item_code"] == "11-OT-00106"
    assert staged_row["sku_normalized"] is True
    assert staged_row["original_item_code"] == "11-OT -00106"


@pytest.mark.asyncio
async def test_stage_initial_stock_sku_spaces_instead_of_hyphens():
    """Verifies that SKU code with spaces instead of hyphens ('11 OT 00256') resolves to canonical '11-OT-00256'."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(
        id=item_id,
        item_code="11-OT-00256",
        description="Office Equipment",
        default_unit="PCS",
        is_active=True,
    )

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"11-OT-00256": item})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["11 OT 00256", "30", "PCS", "120.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="sku_spaces_instead_of_hyphens.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 1
    assert batch.error_rows == 0
    staged_row = batch.staged_data["rows"][0]
    assert staged_row["item_code"] == "11-OT-00256"
    assert staged_row["sku_normalized"] is True
    assert staged_row["original_item_code"] == "11 OT 00256"


@pytest.mark.asyncio
async def test_stage_initial_stock_sku_space_instead_of_first_hyphen():
    """Verifies that SKU code with space instead of first hyphen ('05 TL-00022') resolves to canonical '05-TL-00022'."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(
        id=item_id,
        item_code="05-TL-00022",
        description="Floor Tiles",
        default_unit="M2",
        is_active=True,
    )

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"05-TL-00022": item})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["05 TL-00022", "80", "M2", "420.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="sku_space_first_hyphen.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 1
    assert batch.error_rows == 0
    staged_row = batch.staged_data["rows"][0]
    assert staged_row["item_code"] == "05-TL-00022"
    assert staged_row["sku_normalized"] is True
    assert staged_row["original_item_code"] == "05 TL-00022"


@pytest.mark.asyncio
async def test_stage_initial_stock_truly_non_existent_sku_logs_invalid_item():
    """Verifies that a truly non-existent SKU ('17-CL-00014') logs INVALID_ITEM error."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["17-CL-00014", "20", "PCS", "50.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="nonexistent_sku.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.valid_rows == 0
    assert batch.error_rows == 1
    logged_errors = service.repo.create_errors.call_args[0][0]
    assert any(err.error_code == "INVALID_ITEM" and "17-CL-00014" in (err.raw_value or "") for err in logged_errors)


@pytest.mark.asyncio
async def test_stage_initial_stock_uom_roll_vs_pcs_raises_invalid_uom():
    """Verifies that 'roll' vs 'PCS' raises INVALID_UOM without loose fallback."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(
        id=item_id,
        item_code="05-HW-00010",
        description="Wire Roll",
        default_unit="PCS",
        is_active=True,
    )

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"05-HW-00010": item})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["05-HW-00010", "12", "roll", "150.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="roll_mismatch.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.valid_rows == 0
    assert batch.error_rows == 1
    logged_errors = service.repo.create_errors.call_args[0][0]
    assert any(err.error_code == "INVALID_UOM" and "roll" in (err.raw_value or "") for err in logged_errors)


@pytest.mark.asyncio
async def test_stage_initial_stock_uom_pail_vs_gallon_raises_invalid_uom():
    """Verifies that 'pail' is strictly distinct and raises INVALID_UOM against 'Gallon'."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(
        id=item_id,
        item_code="07-PC-00005",
        description="Gloss Paint",
        default_unit="Gallon",
        is_active=True,
    )

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"07-PC-00005": item})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["07-PC-00005", "5", "pail", "1200.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="pail_mismatch.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.valid_rows == 0
    assert batch.error_rows == 1
    logged_errors = service.repo.create_errors.call_args[0][0]
    assert any(err.error_code == "INVALID_UOM" and "pail" in (err.raw_value or "") for err in logged_errors)


@pytest.mark.asyncio
async def test_stage_initial_stock_uom_ltr_vs_gallon_raises_invalid_uom():
    """Verifies that 'LTR' vs 'Gallon' raises INVALID_UOM because they belong to distinct volume groups."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(
        id=item_id,
        item_code="07-PC-00006",
        description="Enamel Paint",
        default_unit="Gallon",
        is_active=True,
    )

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"07-PC-00006": item})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["07-PC-00006", "10", "LTR", "450.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="ltr_gallon_mismatch.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.valid_rows == 0
    assert batch.error_rows == 1
    logged_errors = service.repo.create_errors.call_args[0][0]
    assert any(err.error_code == "INVALID_UOM" and "LTR" in (err.raw_value or "") for err in logged_errors)


@pytest.mark.asyncio
async def test_stage_initial_stock_uom_safe_synonym_ltr_matches_liter():
    """Verifies that safe 1:1 linguistic synonym 'ltr' matches 'Liter' without error."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(
        id=item_id,
        item_code="07-PC-00007",
        description="Primer Paint",
        default_unit="Liter",
        is_active=True,
    )

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"07-PC-00007": item})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["07-PC-00007", "8", "ltr", "300.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="ltr_synonym.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 1
    assert batch.error_rows == 0
    staged_row = batch.staged_data["rows"][0]
    assert staged_row["unit"] == "Liter"
@pytest.mark.asyncio
async def test_stage_item_master_expanded_categories_clean_and_stationery():
    """Verifies that items under expanded categories (17: CLEAN, 15: STATIONERY, 18: COMPUTER & IT)
    resolve correctly via sheet tab name, category cell alias, and SKU prefix without INVALID_CATEGORY errors.
    """
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    clean_id = uuid4()
    stat_id = uuid4()
    it_id = uuid4()

    clean_cat = Category(id=clean_id, code="17", name="CLEAN", is_active=True)
    stat_cat = Category(id=stat_id, code="15", name="STATIONERY", is_active=True)
    it_cat = Category(id=it_id, code="18", name="COMPUTER & IT", is_active=True)

    categories_map = {
        "17": clean_cat,
        "CLEAN": clean_cat,
        "15": stat_cat,
        "STATIONERY": stat_cat,
        "18": it_cat,
        "COMPUTER & IT": it_cat,
    }

    service.repo.get_all_categories = AsyncMock(return_value=categories_map)
    service.repo.get_existing_item_codes = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "CLEAN": [
            ["Inventory ID", "Description", "Category", "Unit Measurement"],
            ["17-CL-00001", "Liquid Floor Detergent 5L", "CLEAN", "Liter"],
            ["17-CL-00002", "Heavy Duty Cleaning Gloves", "", "Pair"],
            ["17-CL-00003", "Microfiber Cleaning Cloth", "CLEANING", "pcs"],
            ["", "", "", ""],
            ["Total Count: 3", "", "", ""],
        ],
        "STATIONERY": [
            ["Inventory ID", "Description", "Major Category", "Unit"],
            ["15-ST-00001", "Ballpoint Pens Blue 0.7mm", "STATIONERY", "Pkt"],
            ["15-ST-00002", "A4 Copy Paper 80gsm Box", "", ""],
        ],
        "COMPUTERS": [
            ["Inventory ID", "Description", "Category", "Unit"],
            ["18-CP-00001", "Wireless Optical Mouse", "COMPUTER & IT", "PCS"],
            ["18-IT-00002", "Cat6 Network Cable 305m", "COMPUTERS", "ROLL"],
        ],
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_item_master_file(
        user_id=uuid4(),
        file_name="expanded_catalog.xlsx",
        file_bytes=file_bytes,
    )

    assert batch.status == "VALIDATED"
    assert batch.error_rows == 0
    assert batch.valid_rows == 7
    items = batch.staged_data["items"]
    items_by_code = {it["item_code"]: it for it in items}

    # Verify Category 17 (CLEAN)
    assert items_by_code["17-CL-00001"]["category_id"] == str(clean_id)
    assert items_by_code["17-CL-00001"]["category_code"] == "17"
    assert items_by_code["17-CL-00001"]["default_unit"] == "Liter"

    assert items_by_code["17-CL-00002"]["category_id"] == str(clean_id)
    assert items_by_code["17-CL-00002"]["default_unit"] == "Pair"

    assert items_by_code["17-CL-00003"]["category_id"] == str(clean_id)
    assert items_by_code["17-CL-00003"]["default_unit"] == "PCS"

    # Verify Category 15 (STATIONERY)
    assert items_by_code["15-ST-00001"]["category_id"] == str(stat_id)
    assert items_by_code["15-ST-00001"]["default_unit"] == "Pkt"

    assert items_by_code["15-ST-00002"]["category_id"] == str(stat_id)
    assert items_by_code["15-ST-00002"]["default_unit"] == "PCS"

    # Verify Category 18 (COMPUTER & IT)
    assert items_by_code["18-CP-00001"]["category_id"] == str(it_id)
    assert items_by_code["18-CP-00001"]["default_unit"] == "PCS"

    assert items_by_code["18-IT-00002"]["category_id"] == str(it_id)
    assert items_by_code["18-IT-00002"]["default_unit"] == "ROLL"


@pytest.mark.asyncio
async def test_stage_item_master_sku_prefix_inference_for_expanded_categories():
    """Verifies that SKU prefix inference correctly resolves categories 15, 16, 17, and 18
    even when category cell is blank and sheet name is generic.
    """
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    stat_id = uuid4()
    hh_id = uuid4()
    clean_id = uuid4()
    it_id = uuid4()

    stat_cat = Category(id=stat_id, code="15", name="STATIONERY", is_active=True)
    hh_cat = Category(id=hh_id, code="16", name="HOUSEHOLD", is_active=True)
    clean_cat = Category(id=clean_id, code="17", name="CLEAN", is_active=True)
    it_cat = Category(id=it_id, code="18", name="COMPUTER & IT", is_active=True)

    categories_map = {
        "15": stat_cat,
        "16": hh_cat,
        "17": clean_cat,
        "18": it_cat,
    }

    service.repo.get_all_categories = AsyncMock(return_value=categories_map)
    service.repo.get_existing_item_codes = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "Sheet1": [
            ["Item Code", "Item Description", "Category", "Unit"],
            ["15-ST-00020", "Stapler Medium", "", "PCS"],
            ["16-HH-00005", "Ceramic Mug Set", "", "Set"],
            ["17-CL-00014", "Glass Cleaner Spray", "", "Liter"],
            ["18-IT-00010", "USB Flash Drive 64GB", "", "PCS"],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_item_master_file(
        user_id=uuid4(),
        file_name="sku_prefix_test.xlsx",
        file_bytes=file_bytes,
    )

    assert batch.status == "VALIDATED"
    assert batch.error_rows == 0
    assert batch.valid_rows == 4

    items = {it["item_code"]: it for it in batch.staged_data["items"]}
    assert items["15-ST-00020"]["category_id"] == str(stat_id)
    assert items["16-HH-00005"]["category_id"] == str(hh_id)
    assert items["17-CL-00014"]["category_id"] == str(clean_id)
    assert items["18-IT-00010"]["category_id"] == str(it_id)
