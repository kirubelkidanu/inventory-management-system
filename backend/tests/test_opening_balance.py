# backend/tests/test_opening_balance.py
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import io
from unittest.mock import AsyncMock, MagicMock
import uuid
from uuid import uuid4
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt
import openpyxl

from app.api.routes.imports import get_import_service
from app.api.routes.transactions import get_transaction_service
from app.core.config import settings
from app.main import app
from app.models.import_ import ImportBatch, ImportError
from app.models.inventory import InventoryBalance
from app.models.item import Item
from app.models.transaction import StockMovement, Transaction, TransactionLine
from app.models.warehouse import Warehouse
from app.schemas.import_ import ImportBatchRead, InitialStockBatchPreview
from app.schemas.transaction import OpeningBalanceCreate, OpeningBalanceLineCreate, TransactionRead
from app.services.import_ import ImportService
from app.services.transaction import TransactionService


@pytest.fixture
def token_factory():
    def make_token(role: str = "ADMIN", user_id: str = "user-test-ob") -> str:
        return jwt.encode(
            {
                "sub": user_id,
                "email": f"{user_id}@ims.local",
                "role": role,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )

    return make_token


def make_excel_bytes(sheets_data: dict[str, list[list]]) -> bytes:
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
    stream = io.StringIO()
    writer = csv.writer(stream)
    for r in rows:
        writer.writerow(r)
    return stream.getvalue().encode("utf-8")


@pytest.mark.asyncio
async def test_service_opening_balance_creates_posted_adjustment():
    """Verifies that TransactionService.create_and_post_opening_balance creates an atomic POSTED ADJUSTMENT."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    existing_balance = InventoryBalance(
        id=uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("0.0000"),
        quantity_reserved=Decimal("0.0000"),
        updated_at=datetime.now(timezone.utc),
    )

    service.repo.lock_inventory_balances_for_update = AsyncMock(return_value={item_id: existing_balance})
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()
    service.repo.get_or_create_balance = AsyncMock(return_value=existing_balance)
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    payload = OpeningBalanceCreate(
        warehouse_id=wh_id,
        transaction_date=date.today(),
        remarks="Initial stock opening balance",
        lines=[
            OpeningBalanceLineCreate(
                item_id=item_id,
                quantity=Decimal("150.0000"),
                unit="BAG",
                unit_price=Decimal("450.5000"),
                remarks="Opening count",
            )
        ],
    )

    tx = await service.create_and_post_opening_balance(user_id=user_id, payload=payload)

    assert tx.transaction_type == "ADJUSTMENT"
    assert tx.status == "POSTED"
    assert tx.external_reference == "OPENING_BALANCE"
    assert tx.adjustment_reason == "Opening Balance"
    assert len(tx.lines) == 1
    assert tx.lines[0].unit_price == Decimal("450.5000")
    assert existing_balance.quantity_on_hand == Decimal("150.0000")

    service.repo.create_transaction.assert_called_once()
    service.repo.create_transaction_lines.assert_called_once()
    service.repo.create_stock_movement.assert_called_once_with(
        transaction_id=tx.id,
        transaction_line_id=tx.lines[0].id,
        item_id=item_id,
        warehouse_id=wh_id,
        project_id=None,
        movement_type="IN",
        quantity=Decimal("150.0000"),
        running_balance=Decimal("150.0000"),
        movement_date=date.today(),
    )
    service.repo.create_audit_log.assert_called_once()
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_opening_balance_validates_inputs():
    """Verifies validations for line quantity, unit price, and item uniqueness."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)
    wh_id = uuid4()
    item_id = uuid4()

    # Empty lines rejected
    with pytest.raises(Exception):
        OpeningBalanceCreate(
            warehouse_id=wh_id,
            lines=[],
        )

    # Duplicate items in lines rejected (ADR-006)
    with pytest.raises(ValueError) as exc:
        OpeningBalanceCreate(
            warehouse_id=wh_id,
            lines=[
                OpeningBalanceLineCreate(item_id=item_id, quantity=Decimal("10"), unit="BAG"),
                OpeningBalanceLineCreate(item_id=item_id, quantity=Decimal("20"), unit="BAG"),
            ],
        )
    assert "Duplicate item" in str(exc.value)

    # Negative price rejected
    with pytest.raises(Exception):
        OpeningBalanceLineCreate(item_id=item_id, quantity=Decimal("10"), unit="BAG", unit_price=Decimal("-5"))


@pytest.mark.asyncio
async def test_stage_4_column_opening_balance_spreadsheet():
    """Verifies staging a 4-column spreadsheet with header variations, default UOM fallback, and unit price."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item1_id = uuid4()
    item2_id = uuid4()
    wh = Warehouse(id=wh_id, code="KZ-WH-001", name="Kazanchis Store", is_active=True)
    item1 = Item(id=item1_id, item_code="01-CM-00001", description="Cement 42.5N", default_unit="BAG", is_active=True)
    item2 = Item(id=item2_id, item_code="02-ST-00001", description="Rebar 12mm", default_unit="PCS", is_active=True)

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"01-CM-00001": item1, "02-ST-00001": item2})
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value=set())
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    excel_data = {
        "Sheet1": [
            ["inventory id", "quantity", "unit measurment", "unit price"],
            ["01-CM-00001", "1200", "BAG", "550.00"],
            ["02-ST-00001", "300", "", ""],  # Blank UOM & price -> fallback to PCS & 0.0000
        ]
    }
    file_bytes = make_excel_bytes(excel_data)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="4col_opening.xlsx",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
        transaction_date=date.today(),
        remarks="Opening stock 4-col import",
    )

    assert batch.status == "VALIDATED"
    assert batch.valid_rows == 2
    assert batch.error_rows == 0

    rows = batch.staged_data["rows"]
    assert rows[0]["item_code"] == "01-CM-00001"
    assert rows[0]["unit"] == "BAG"
    assert rows[0]["unit_price"] == "550.00"
    assert rows[0]["total_price"] == "660000.0000"

    assert rows[1]["item_code"] == "02-ST-00001"
    assert rows[1]["unit"] == "PCS"
    assert rows[1]["unit_price"] == "0.0000"
    assert rows[1]["total_price"] == "0.0000"

    assert batch.staged_data["total_value"] == "660000.0000"


@pytest.mark.asyncio
async def test_stage_duplicate_in_file_and_already_exists():
    """Verifies that duplicate items in the same file are marked DUPLICATE_IN_FILE and existing balances marked ALREADY_EXISTS."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    wh_id = uuid4()
    item1_id = uuid4()
    wh = Warehouse(id=wh_id, code="KZ-WH-001", name="Kazanchis Store", is_active=True)
    item1 = Item(id=item1_id, item_code="01-CM-00001", description="Cement 42.5N", default_unit="BAG", is_active=True)

    service.repo.get_warehouse_by_id = AsyncMock(return_value=wh)
    service.repo.get_items_by_codes = AsyncMock(return_value={"01-CM-00001": item1})
    # item1 already has an opening balance in this warehouse!
    service.repo.get_existing_opening_balance_item_ids = AsyncMock(return_value={item1_id})
    service.repo.create_batch = AsyncMock()
    service.repo.create_errors = AsyncMock()

    csv_rows = [
        ["inventory id", "qty", "uom", "unit_cost"],
        ["01-CM-00001", "100", "BAG", "500.00"],
        ["01-CM-00001", "200", "BAG", "500.00"],
    ]
    file_bytes = make_csv_bytes(csv_rows)

    batch = await service.stage_initial_stock_file(
        user_id=uuid4(),
        file_name="opening_dups.csv",
        file_bytes=file_bytes,
        warehouse_id=wh_id,
    )

    logged_errors = service.repo.create_errors.call_args[0][0]
    error_codes = [err.error_code for err in logged_errors]
    assert "ALREADY_EXISTS" in error_codes
    assert "DUPLICATE_IN_FILE" in error_codes
    assert batch.valid_rows == 0


@pytest.mark.asyncio
async def test_commit_initial_stock_routes_through_transaction_service():
    """Verifies that commit_initial_stock_import routes through TransactionService.create_and_post_opening_balance."""
    mock_session = AsyncMock()
    service = ImportService(mock_session)

    batch_id = uuid4()
    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    batch = ImportBatch(
        id=batch_id,
        batch_number="IMP-STOCK-20261031-12345678",
        import_type="INITIAL_STOCK",
        file_name="opening.xlsx",
        file_size_bytes=1024,
        total_rows=1,
        valid_rows=1,
        error_rows=0,
        status="VALIDATED",
        staged_data={
            "transaction_date": "2026-10-31",
            "remarks": "Opening stock commit test",
            "rows": [
                {
                    "row_number": 2,
                    "warehouse_id": str(wh_id),
                    "warehouse_code": "KZ-WH-001",
                    "item_id": str(item_id),
                    "item_code": "01-CM-00001",
                    "quantity": "500.0000",
                    "unit": "BAG",
                    "unit_price": "550.0000",
                    "total_price": "275000.0000",
                    "project_id": None,
                    "remarks": "Opening stock",
                }
            ],
        },
        created_by=user_id,
        created_at=datetime.now(timezone.utc),
    )

    service.repo.get_batch_by_id = AsyncMock(return_value=batch)
    service.repo.update_batch = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    mock_tx = Transaction(
        id=uuid4(),
        transaction_number="ADJ-20261031-A1B2C3D4",
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
    assert result["imported_rows"] == 1
    assert result["transactions_created"] == 1
    assert result["transaction_numbers"] == ["ADJ-20261031-A1B2C3D4"]
    assert batch.status == "COMPLETED"

    service.tx_service.create_and_post_opening_balance.assert_called_once()
    call_kwargs = service.tx_service.create_and_post_opening_balance.call_args[1]
    assert call_kwargs["payload"].warehouse_id == wh_id
    assert call_kwargs["payload"].lines[0].unit_price == Decimal("550.0000")
    assert call_kwargs["commit_session"] is False
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_api_manual_opening_balance_endpoint(token_factory):
    """Verifies POST /api/v1/transactions/opening-balance via FastAPI route."""
    wh_id = uuid4()
    item_id = uuid4()
    tx_id = uuid4()

    mock_tx = Transaction(
        id=tx_id,
        transaction_number="ADJ-20261031-OPEN0001",
        transaction_type="ADJUSTMENT",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=wh_id,
        adjustment_reason="Opening Balance",
        external_reference="OPENING_BALANCE",
        remarks="API Test Opening Balance",
        created_by=uuid4(),
        created_at=datetime.now(timezone.utc),
        lines=[
            TransactionLine(
                id=uuid4(),
                transaction_id=tx_id,
                line_number=1,
                item_id=item_id,
                quantity=Decimal("100.0000"),
                unit="BAG",
                unit_price=Decimal("500.0000"),
            )
        ],
    )

    mock_tx_service = AsyncMock()
    mock_tx_service.create_and_post_opening_balance = AsyncMock(return_value=mock_tx)

    app.dependency_overrides[get_transaction_service] = lambda: mock_tx_service

    token = token_factory(role="INVENTORY_MANAGER")
    payload = {
        "warehouse_id": str(wh_id),
        "transaction_date": str(date.today()),
        "remarks": "API Test Opening Balance",
        "lines": [
            {
                "item_id": str(item_id),
                "quantity": "100.0000",
                "unit": "BAG",
                "unit_price": "500.0000",
            }
        ],
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/transactions/opening-balance",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["transaction_number"] == "ADJ-20261031-OPEN0001"
    assert data["transaction_type"] == "ADJUSTMENT"
    assert data["status"] == "POSTED"
    assert data["external_reference"] == "OPENING_BALANCE"
    assert data["adjustment_reason"] == "Opening Balance"
    assert len(data["lines"]) == 1
    assert Decimal(str(data["lines"][0]["unit_price"])) == Decimal("500.0000")
    assert Decimal(str(data["lines"][0]["total_price"])) == Decimal("50000.0000")


@pytest.mark.asyncio
async def test_api_stage_and_batches_endpoints(token_factory):
    """Verifies POST /api/v1/imports/initial-stock/stage and GET /api/v1/imports/initial-stock/batches."""
    batch_id = uuid4()
    mock_batch = ImportBatch(
        id=batch_id,
        batch_number="IMP-STOCK-20261031-STAGE01",
        import_type="INITIAL_STOCK",
        file_name="stock.xlsx",
        file_size_bytes=1024,
        total_rows=1,
        valid_rows=1,
        error_rows=0,
        status="VALIDATED",
        created_by=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    mock_import_service = AsyncMock()
    mock_import_service.stage_initial_stock_file = AsyncMock(return_value=mock_batch)
    mock_preview = InitialStockBatchPreview(
        batch=ImportBatchRead.model_validate(mock_batch),
        errors=[],
        valid_rows_sample=[],
        total_value=Decimal("0.0000"),
    )
    mock_import_service.get_initial_stock_batch_preview = AsyncMock(return_value=mock_preview)
    mock_import_service.list_initial_stock_batches = AsyncMock(return_value=[mock_batch])

    app.dependency_overrides[get_import_service] = lambda: mock_import_service

    token = token_factory(role="INVENTORY_MANAGER")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test stage endpoint with warehouse_id form field
        stage_res = await client.post(
            "/api/v1/imports/initial-stock/stage",
            headers={"Authorization": f"Bearer {token}"},
            data={"warehouse_id": str(uuid4())},
            files={"file": ("stock.xlsx", b"dummy_content", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert stage_res.status_code == 201
        assert stage_res.json()["batch_number"] == "IMP-STOCK-20261031-STAGE01"

        # Test list batches endpoint
        batches_res = await client.get(
            "/api/v1/imports/initial-stock/batches",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert batches_res.status_code == 200
        assert len(batches_res.json()) == 1

    app.dependency_overrides.clear()
