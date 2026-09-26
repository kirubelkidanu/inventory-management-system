# backend/tests/test_initial_stock_import.py
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
from app.models.import_ import ImportBatch, ImportError
from app.models.inventory import InventoryBalance
from app.models.item import Item
from app.models.project import Project
from app.models.transaction import StockMovement, Transaction, TransactionLine
from app.models.warehouse import Warehouse
from app.schemas.import_ import (
    ImportBatchRead,
    ImportErrorRead,
    InitialStockBatchPreview,
    InitialStockRow,
)
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

    async def stage_initial_stock_file(self, user_id, file_name: str, file_bytes: bytes):
        self.stage_calls.append((user_id, file_name, file_bytes))
        batch_id = uuid4()
        return ImportBatch(
            id=batch_id,
            batch_number=f"IMP-STOCK-20260918-{uuid4().hex[:8].upper()}",
            import_type="INITIAL_STOCK",
            file_name=file_name,
            file_size_bytes=len(file_bytes),
            total_rows=1,
            valid_rows=1,
            error_rows=0,
            status="VALIDATED",
            staged_data={
                "rows": [
                    {
                        "row_number": 2,
                        "warehouse_code": "WH-MAIN",
                        "item_code": "01-CM-00001",
                        "quantity": "100.0000",
                        "unit": "BAG",
                    }
                ]
            },
            created_by=_to_uuid(user_id),
            created_at=datetime.now(timezone.utc),
        )

    async def get_initial_stock_batch_preview(self, batch_id):
        batch = ImportBatch(
            id=batch_id,
            batch_number="IMP-STOCK-20260918-ABCD1234",
            import_type="INITIAL_STOCK",
            file_name="initial_stock.xlsx",
            file_size_bytes=1024,
            total_rows=1,
            valid_rows=1,
            error_rows=0,
            status="VALIDATED",
            created_by=uuid4(),
            created_at=datetime.now(timezone.utc),
        )
        return InitialStockBatchPreview(
            batch=ImportBatchRead.model_validate(batch),
            errors=[],
            valid_rows_sample=[
                {
                    "warehouse_code": "WH-MAIN",
                    "item_code": "01-CM-00001",
                    "quantity": "100.0000",
                    "unit": "BAG",
                }
            ],
        )

    async def commit_initial_stock_import(self, user_id, batch_id):
        self.commit_calls.append((user_id, batch_id))
        return {
            "message": "Initial stock import completed successfully.",
            "batch_id": batch_id,
            "batch_number": "IMP-STOCK-20260918-ABCD1234",
            "imported_rows": 1,
            "warehouses_affected": 1,
            "transactions_created": 1,
            "transaction_numbers": ["GRV-20260918-TEST1234"],
        }


# ==============================================================================
# Service Unit Tests: Staging & Validation
# ==============================================================================


@pytest.mark.asyncio
async def test_stage_valid_excel_initial_stock():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    proj_id = uuid4()

    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(
        id=item_id,
        item_code="01-CM-00001",
        description="Portland Cement",
        category_id=uuid4(),
        default_unit="BAG",
        is_active=True,
    )
    proj = Project(id=proj_id, code="PRJ-01", name="Bridge Construction", is_active=True)

    service.repo.get_warehouses_by_codes = AsyncMock(return_value={"WH-001": wh})
    service.repo.get_items_by_codes = AsyncMock(return_value={"01-CM-00001": item})
    service.repo.get_projects_by_codes = AsyncMock(return_value={"PRJ-01": proj})
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "OpeningStock": [
            ["Warehouse Code", "Item Code", "Quantity", "Unit", "Project Code", "Remarks"],
            ["WH-001", "01-CM-00001", "250.5", "BAG", "PRJ-01", "Opening inventory count"],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)
    user_id = uuid4()

    batch = await service.stage_initial_stock_file(
        user_id=user_id, file_name="opening_stock.xlsx", file_bytes=file_bytes
    )

    assert batch.status == "VALIDATED"
    assert batch.import_type == "INITIAL_STOCK"
    assert batch.total_rows == 1
    assert batch.valid_rows == 1
    assert batch.error_rows == 0
    assert len(batch.staged_data["rows"]) == 1
    staged = batch.staged_data["rows"][0]
    assert staged["warehouse_id"] == str(wh_id)
    assert staged["warehouse_code"] == "WH-001"
    assert staged["item_id"] == str(item_id)
    assert staged["item_code"] == "01-CM-00001"
    assert staged["quantity"] == "250.5"
    assert staged["unit"] == "BAG"
    assert staged["project_id"] == str(proj_id)
    assert staged["remarks"] == "Opening inventory count"

    service.repo.create_batch.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_stage_valid_csv_initial_stock():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh = Warehouse(id=uuid4(), code="WH-002", name="Branch Warehouse", is_active=True)
    item = Item(
        id=uuid4(),
        item_code="02-ST-00001",
        description="Steel Rebar 12mm",
        category_id=uuid4(),
        default_unit="PCS",
        is_active=True,
    )

    service.repo.get_warehouses_by_codes = AsyncMock(return_value={"WH-002": wh})
    service.repo.get_items_by_codes = AsyncMock(return_value={"02-ST-00001": item})
    service.repo.get_projects_by_codes = AsyncMock(return_value={})
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["warehouse", "item_code", "qty", "unit"],
        ["WH-002", "02-ST-00001", "500", "PCS"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(), file_name="stock.csv", file_bytes=file_bytes
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 1
    assert batch.error_rows == 0
    assert batch.staged_data["rows"][0]["item_code"] == "02-ST-00001"
    assert batch.staged_data["rows"][0]["quantity"] == "500"


@pytest.mark.asyncio
async def test_stage_validation_errors_warehouse_item_quantity_duplicate():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh = Warehouse(id=uuid4(), code="WH-001", name="Main Warehouse", is_active=True)
    item1 = Item(
        id=uuid4(),
        item_code="01-CM-00001",
        description="Portland Cement",
        category_id=uuid4(),
        default_unit="BAG",
        is_active=True,
    )
    item2 = Item(
        id=uuid4(),
        item_code="01-CM-00002",
        description="Rapid Hardening Cement",
        category_id=uuid4(),
        default_unit="BAG",
        is_active=True,
    )
    item3 = Item(
        id=uuid4(),
        item_code="01-CM-00003",
        description="White Cement",
        category_id=uuid4(),
        default_unit="BAG",
        is_active=True,
    )
    item4 = Item(
        id=uuid4(),
        item_code="01-CM-00004",
        description="Masonry Cement",
        category_id=uuid4(),
        default_unit="BAG",
        is_active=True,
    )

    # Repository returns WH-001 and items
    service.repo.get_warehouses_by_codes = AsyncMock(return_value={"WH-001": wh})
    service.repo.get_items_by_codes = AsyncMock(
        return_value={
            "01-CM-00001": item1,
            "01-CM-00002": item2,
            "01-CM-00003": item3,
            "01-CM-00004": item4,
        }
    )
    service.repo.get_projects_by_codes = AsyncMock(return_value={})
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "Sheet1": [
            ["Warehouse Code", "Item Code", "Quantity", "Unit"],
            # Row 2: Invalid Warehouse
            ["WH-NONEXISTENT", "01-CM-00001", "10", "BAG"],
            # Row 3: Invalid Item
            ["WH-001", "ITEM-NONEXISTENT", "10", "BAG"],
            # Row 4: Negative Quantity
            ["WH-001", "01-CM-00002", "-5", "BAG"],
            # Row 5: Zero Quantity
            ["WH-001", "01-CM-00003", "0", "BAG"],
            # Row 6: Unit mismatch
            ["WH-001", "01-CM-00004", "15", "KG"],
            # Row 7: Valid entry
            ["WH-001", "01-CM-00001", "100", "BAG"],
            # Row 8: Duplicate entry for same warehouse and item
            ["WH-001", "01-CM-00001", "50", "BAG"],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(), file_name="stock_errors.xlsx", file_bytes=file_bytes
    )

    assert batch.status == "PARSED"
    assert batch.valid_rows == 1  # only row 7 is valid
    assert batch.error_rows > 0

    service.repo.create_errors.assert_called_once()
    logged_errors = service.repo.create_errors.call_args[0][0]
    error_codes = [err.error_code for err in logged_errors]

    assert "INVALID_WAREHOUSE" in error_codes
    assert "INVALID_ITEM" in error_codes
    assert "INVALID_QUANTITY" in error_codes
    assert "INVALID_UOM" in error_codes
    assert "DUPLICATE_ENTRY" in error_codes


@pytest.mark.asyncio
async def test_stage_catches_invalid_project_code():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh = Warehouse(id=uuid4(), code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(
        id=uuid4(),
        item_code="01-CM-00001",
        description="Portland Cement",
        category_id=uuid4(),
        default_unit="BAG",
        is_active=True,
    )

    service.repo.get_warehouses_by_codes = AsyncMock(return_value={"WH-001": wh})
    service.repo.get_items_by_codes = AsyncMock(return_value={"01-CM-00001": item})
    service.repo.get_projects_by_codes = AsyncMock(return_value={})  # project not found
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "Sheet1": [
            ["Warehouse Code", "Item Code", "Quantity", "Unit", "Project Code"],
            ["WH-001", "01-CM-00001", "10", "BAG", "PRJ-UNKNOWN"],
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(), file_name="project_error.xlsx", file_bytes=file_bytes
    )

    assert batch.status == "PARSED"
    assert batch.valid_rows == 0
    assert batch.error_rows == 1
    logged_errors = service.repo.create_errors.call_args[0][0]
    assert any(e.error_code == "INVALID_PROJECT" for e in logged_errors)


@pytest.mark.asyncio
async def test_stage_unsupported_file_format():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    with pytest.raises(HTTPException) as exc:
        await service.stage_initial_stock_file(
            user_id=uuid4(), file_name="stock.pdf", file_bytes=b"dummy content"
        )
    assert exc.value.status_code == 400
    assert "Unsupported file format" in exc.value.detail


@pytest.mark.asyncio
async def test_stage_empty_file_rows():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    csv_bytes = make_csv_bytes([])
    with pytest.raises(HTTPException) as exc:
        await service.stage_initial_stock_file(
            user_id=uuid4(), file_name="empty.csv", file_bytes=csv_bytes
        )
    assert exc.value.status_code == 400
    assert "contains no data rows" in exc.value.detail


# ==============================================================================
# Service Unit Tests: Commit & Atomic Ledger Writes
# ==============================================================================


@pytest.mark.asyncio
async def test_commit_initial_stock_atomic_posting():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    batch_id = uuid4()
    user_id = uuid4()
    wh1_id = uuid4()
    wh2_id = uuid4()
    item1_id = uuid4()
    item2_id = uuid4()

    batch = ImportBatch(
        id=batch_id,
        batch_number="IMP-STOCK-20260918-12345678",
        import_type="INITIAL_STOCK",
        file_name="opening.xlsx",
        file_size_bytes=2048,
        total_rows=2,
        valid_rows=2,
        error_rows=0,
        status="VALIDATED",
        staged_data={
            "rows": [
                {
                    "row_number": 2,
                    "warehouse_id": str(wh1_id),
                    "warehouse_code": "WH-001",
                    "item_id": str(item1_id),
                    "item_code": "01-CM-00001",
                    "quantity": "100.0000",
                    "unit": "BAG",
                    "project_id": None,
                    "remarks": "Wh1 Line",
                },
                {
                    "row_number": 3,
                    "warehouse_id": str(wh2_id),
                    "warehouse_code": "WH-002",
                    "item_id": str(item2_id),
                    "item_code": "02-ST-00001",
                    "quantity": "50.0000",
                    "unit": "PCS",
                    "project_id": None,
                    "remarks": "Wh2 Line",
                },
            ]
        },
        created_by=user_id,
        created_at=datetime.now(timezone.utc),
    )

    service.repo.get_batch_by_id = AsyncMock(return_value=batch)
    service.repo.update_batch = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    bal1 = InventoryBalance(
        id=uuid4(), warehouse_id=wh1_id, item_id=item1_id, quantity_on_hand=Decimal("0.0000")
    )
    bal2 = InventoryBalance(
        id=uuid4(), warehouse_id=wh2_id, item_id=item2_id, quantity_on_hand=Decimal("10.0000")
    )

    service.tx_repo.create_transaction = AsyncMock()
    service.tx_repo.lock_inventory_balances_for_update = AsyncMock(return_value={})
    service.tx_repo.create_transaction_lines = AsyncMock()
    service.tx_repo.get_or_create_balance = AsyncMock(side_effect=[bal1, bal2])
    service.tx_repo.create_stock_movement = AsyncMock()
    service.tx_repo.create_audit_log = AsyncMock()

    result = await service.commit_initial_stock_import(user_id=user_id, batch_id=batch_id)

    assert result["batch_id"] == batch_id
    assert result["imported_rows"] == 2
    assert result["warehouses_affected"] == 2
    assert result["transactions_created"] == 2
    assert len(result["transaction_numbers"]) == 2
    for tx_num in result["transaction_numbers"]:
        assert tx_num.startswith("GRV-")

    assert batch.status == "COMPLETED"
    assert batch.completed_at is not None
    service.repo.update_batch.assert_called_once_with(batch)
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_commit_initial_stock_rejects_already_completed():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    batch_id = uuid4()
    batch = ImportBatch(
        id=batch_id,
        batch_number="IMP-STOCK-20260918-12345678",
        import_type="INITIAL_STOCK",
        file_name="opening.xlsx",
        file_size_bytes=2048,
        total_rows=1,
        valid_rows=1,
        error_rows=0,
        status="COMPLETED",
        staged_data={"rows": [{"item_code": "01-CM-00001"}]},
        created_by=uuid4(),
        created_at=datetime.now(timezone.utc),
    )
    service.repo.get_batch_by_id = AsyncMock(return_value=batch)

    with pytest.raises(HTTPException) as exc:
        await service.commit_initial_stock_import(user_id=uuid4(), batch_id=batch_id)

    assert exc.value.status_code == 400
    assert "already been committed" in exc.value.detail


@pytest.mark.asyncio
async def test_commit_initial_stock_rejects_wrong_import_type():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    batch_id = uuid4()
    batch = ImportBatch(
        id=batch_id,
        batch_number="IMP-ITEM-20260918-12345678",
        import_type="ITEM_MASTER",  # wrong type
        file_name="items.xlsx",
        file_size_bytes=2048,
        total_rows=1,
        valid_rows=1,
        error_rows=0,
        status="VALIDATED",
        staged_data={"items": []},
        created_by=uuid4(),
        created_at=datetime.now(timezone.utc),
    )
    service.repo.get_batch_by_id = AsyncMock(return_value=batch)

    with pytest.raises(HTTPException) as exc:
        await service.commit_initial_stock_import(user_id=uuid4(), batch_id=batch_id)

    assert exc.value.status_code == 400
    assert "expected 'INITIAL_STOCK'" in exc.value.detail


@pytest.mark.asyncio
async def test_commit_initial_stock_rejects_empty_rows():
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    batch_id = uuid4()
    batch = ImportBatch(
        id=batch_id,
        batch_number="IMP-STOCK-20260918-12345678",
        import_type="INITIAL_STOCK",
        file_name="empty.xlsx",
        file_size_bytes=2048,
        total_rows=0,
        valid_rows=0,
        error_rows=0,
        status="PARSED",
        staged_data={"rows": []},
        created_by=uuid4(),
        created_at=datetime.now(timezone.utc),
    )
    service.repo.get_batch_by_id = AsyncMock(return_value=batch)

    with pytest.raises(HTTPException) as exc:
        await service.commit_initial_stock_import(user_id=uuid4(), batch_id=batch_id)

    assert exc.value.status_code == 400
    assert "No valid initial stock rows" in exc.value.detail


# ==============================================================================
# API Endpoints & RBAC Security Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_api_upload_initial_stock_success(token_factory):
    fake_service = FakeImportService()
    app.dependency_overrides[get_import_service] = lambda: fake_service

    token = token_factory(role="ADMIN")
    csv_bytes = make_csv_bytes([["warehouse", "item", "qty", "unit"], ["WH-01", "IT-01", "10", "BAG"]])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/imports/initial-stock/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("initial.csv", csv_bytes, "text/csv")},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 201
    data = response.json()
    assert data["import_type"] == "INITIAL_STOCK"
    assert data["status"] == "VALIDATED"
    assert len(fake_service.stage_calls) == 1


@pytest.mark.asyncio
async def test_api_get_initial_stock_preview(token_factory):
    fake_service = FakeImportService()
    app.dependency_overrides[get_import_service] = lambda: fake_service

    token = token_factory(role="INVENTORY_MANAGER")
    batch_id = uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/imports/initial-stock/{batch_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["batch"]["import_type"] == "INITIAL_STOCK"
    assert len(data["valid_rows_sample"]) == 1
    assert data["valid_rows_sample"][0]["warehouse_code"] == "WH-MAIN"


@pytest.mark.asyncio
async def test_api_commit_initial_stock_success(token_factory):
    fake_service = FakeImportService()
    app.dependency_overrides[get_import_service] = lambda: fake_service

    token = token_factory(role="INVENTORY_MANAGER")
    batch_id = uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/imports/initial-stock/{batch_id}/commit",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Initial stock import completed successfully."
    assert data["imported_rows"] == 1
    assert len(fake_service.commit_calls) == 1


@pytest.mark.asyncio
async def test_api_initial_stock_rbac_forbidden_for_store_keeper_and_viewer(token_factory):
    fake_service = FakeImportService()
    app.dependency_overrides[get_import_service] = lambda: fake_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for forbidden_role in ("STORE_KEEPER", "VIEWER"):
            token = token_factory(role=forbidden_role)

            # Upload attempt
            upload_res = await client.post(
                "/api/v1/imports/initial-stock/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("stock.csv", b"dummy", "text/csv")},
            )
            assert upload_res.status_code == 403

            # Commit attempt
            commit_res = await client.post(
                f"/api/v1/imports/initial-stock/{uuid4()}/commit",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert commit_res.status_code == 403

            # Preview attempt
            preview_res = await client.get(
                f"/api/v1/imports/initial-stock/{uuid4()}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert preview_res.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_initial_stock_unauthenticated_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # No Authorization header
        res_upload = await client.post(
            "/api/v1/imports/initial-stock/upload",
            files={"file": ("stock.csv", b"dummy", "text/csv")},
        )
        assert res_upload.status_code in (401, 403)

        res_commit = await client.post(f"/api/v1/imports/initial-stock/{uuid4()}/commit")
        assert res_commit.status_code in (401, 403)

        res_preview = await client.get(f"/api/v1/imports/initial-stock/{uuid4()}")
        assert res_preview.status_code in (401, 403)
