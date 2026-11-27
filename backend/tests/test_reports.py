# backend/tests/test_reports.py
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import io
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from jose import jwt
import openpyxl
import pytest

from app.api.routes.reports import get_report_service
from app.core.config import settings
from app.main import app
from app.schemas.report import (
    InTransitReportItem,
    StockBalanceItem,
    StockBalanceResponse,
    TrialBalanceItem,
    TrialBalanceResponse,
)
from app.services.report import ReportService


@pytest.fixture
def token_factory():
    def make_token(role: str = "VIEWER", user_id: str = "user-123") -> str:
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


class FakeReportService:
    async def get_trial_balance_report(
        self,
        date_from=None,
        date_to=None,
        warehouse_id=None,
        project_id=None,
        item_id=None,
        category_id=None,
        transaction_type=None,
        search=None,
        page=1,
        page_size=50,
    ):
        item = TrialBalanceItem(
            movement_id=uuid4(),
            movement_date=date.today(),
            created_at=datetime.now(timezone.utc),
            transaction_id=uuid4(),
            transaction_number="GRV-20260918-0001",
            transaction_type="GRV",
            reference_number="INV-999",
            item_id=uuid4(),
            item_code="01-CM-00001",
            item_description="Portland Cement 42.5N",
            category_name="CEMENT",
            unit="BAG",
            warehouse_id=uuid4(),
            warehouse_code="WH001",
            warehouse_name="Main Warehouse",
            project_name="Kazanchis",
            plate_no="3-A12345",
            driver_name="Abebe Bikila",
            in_quantity=Decimal("100.0000"),
            out_quantity=Decimal("0.0000"),
            signed_quantity=Decimal("100.0000"),
            running_balance=Decimal("100.0000"),
            status="POSTED",
            entered_by_name="Store Clerk",
        )
        return TrialBalanceResponse(
            total_count=1,
            page=page,
            page_size=page_size,
            items=[item],
            total_in=Decimal("100.0000"),
            total_out=Decimal("0.0000"),
        )

    async def export_trial_balance_excel(
        self,
        date_from=None,
        date_to=None,
        warehouse_id=None,
        project_id=None,
        item_id=None,
        category_id=None,
        transaction_type=None,
        search=None,
    ):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Trial Balance"
        ws.append(["Date", "Tx Number", "IN", "OUT"])
        ws.append(["2026-09-18", "GRV-001", 100.0, 0.0])
        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream

    async def get_stock_balance_report(
        self,
        warehouse_id=None,
        category_id=None,
        search=None,
    ):
        item = StockBalanceItem(
            warehouse_id=uuid4(),
            warehouse_code="WH001",
            warehouse_name="Main Warehouse",
            project_name="Kazanchis",
            category_name="CEMENT",
            item_id=uuid4(),
            item_code="01-CM-00001",
            item_description="Portland Cement 42.5N",
            unit="BAG",
            quantity_on_hand=Decimal("100.0000"),
            quantity_reserved=Decimal("20.0000"),
            quantity_available=Decimal("80.0000"),
        )
        return StockBalanceResponse(total_count=1, items=[item])

    async def get_in_transit_report(
        self,
        source_warehouse_id=None,
        destination_warehouse_id=None,
        status=None,
        search=None,
        **kwargs,
    ):
        item = InTransitReportItem(
            transfer_record_id=uuid4(),
            istv_transaction_id=uuid4(),
            istv_number="ISTV-20260918-0001",
            transaction_date=date.today(),
            source_warehouse_name="WH001",
            destination_warehouse_name="WH002",
            plate_no="3-B54321",
            driver_name="Tariku Tesfaye",
            status="IN_TRANSIT",
            item_id=uuid4(),
            item_code="01-CM-00001",
            item_description="Portland Cement",
            unit="BAG",
            sent_quantity=Decimal("50.0000"),
            received_quantity=Decimal("10.0000"),
            remaining_quantity=Decimal("40.0000"),
        )
        return [item]


# ===========================================================================
# 1. Service Layer Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_service_trial_balance_report():
    mock_session = AsyncMock()
    service = ReportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    tx_id = uuid4()
    mov_id1 = uuid4()
    mov_id2 = uuid4()

    fake_rows = [
        {
            "movement_id": mov_id1,
            "movement_date": date(2026, 9, 1),
            "created_at": datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            "transaction_id": tx_id,
            "transaction_number": "GRV-001",
            "transaction_type": "GRV",
            "invoice_no": "INV-101",
            "received_grv_no": None,
            "siv_no": None,
            "requested_no": None,
            "istv_no": None,
            "external_reference": None,
            "item_id": item_id,
            "item_code": "01-CM-00001",
            "item_description": "Cement 42.5N",
            "category_name": "CEMENT",
            "unit": "BAG",
            "warehouse_id": wh_id,
            "warehouse_code": "WH001",
            "warehouse_name": "Main Warehouse",
            "project_name": "Kazanchis",
            "plate_no": None,
            "driver_name": None,
            "movement_type": "IN",
            "quantity": Decimal("150.0000"),
            "signed_quantity": Decimal("150.0000"),
            "running_balance": Decimal("150.0000"),
            "status": "POSTED",
            "entered_by_name": "Admin User",
            "unit_price": Decimal("8133.0000"),
        },
        {
            "movement_id": mov_id2,
            "movement_date": date(2026, 9, 2),
            "created_at": datetime(2026, 9, 2, 11, 0, tzinfo=timezone.utc),
            "transaction_id": uuid4(),
            "transaction_number": "SIV-001",
            "transaction_type": "SIV",
            "invoice_no": None,
            "received_grv_no": None,
            "siv_no": "SIV-202",
            "requested_no": None,
            "istv_no": None,
            "external_reference": None,
            "item_id": item_id,
            "item_code": "01-CM-00001",
            "item_description": "Cement 42.5N",
            "category_name": "CEMENT",
            "unit": "BAG",
            "warehouse_id": wh_id,
            "warehouse_code": "WH001",
            "warehouse_name": "Main Warehouse",
            "project_name": "Kazanchis",
            "plate_no": None,
            "driver_name": None,
            "movement_type": "OUT",
            "quantity": Decimal("40.0000"),
            "signed_quantity": Decimal("-40.0000"),
            "running_balance": Decimal("110.0000"),
            "status": "POSTED",
            "entered_by_name": "Store Keeper",
        },
    ]

    service.repo.get_trial_balance = AsyncMock(
        return_value=(fake_rows, 2, Decimal("150.0000"), Decimal("40.0000"))
    )

    response = await service.get_trial_balance_report(
        warehouse_id=wh_id, page=1, page_size=50
    )

    assert response.total_count == 2
    assert response.total_in == Decimal("150.0000")
    assert response.total_out == Decimal("40.0000")
    assert len(response.items) == 2

    # Verify IN row mapping
    in_row = response.items[0]
    assert in_row.in_quantity == Decimal("150.0000")
    assert in_row.out_quantity == Decimal("0.0000")
    assert in_row.reference_number == "INV-101"
    assert in_row.unit_price == Decimal("8133.0000")
    assert in_row.total_price == Decimal("1219950.0000")

    # Verify OUT row mapping
    out_row = response.items[1]
    assert out_row.in_quantity == Decimal("0.0000")
    assert out_row.out_quantity == Decimal("40.0000")
    assert out_row.signed_quantity == Decimal("-40.0000")
    assert out_row.reference_number == "SIV-202"
    assert out_row.unit_price is None
    assert out_row.total_price is None

    # Total valuation
    assert response.total_valuation == Decimal("1219950.0000")


@pytest.mark.asyncio
async def test_service_trial_balance_renders_srv_in_quantity_unit_price_and_total_value():
    """Confirms SRV Store Return Voucher movements render in_quantity, unit_price, and calculated total_price in Trial Balance."""
    mock_session = AsyncMock()
    service = ReportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()

    fake_srv_row = {
        "movement_id": uuid4(),
        "movement_date": date.today(),
        "created_at": datetime.now(timezone.utc),
        "transaction_id": uuid4(),
        "transaction_number": "SRV-20261105-9999",
        "transaction_type": "SRV",
        "external_reference": None,
        "supplier_name": None,
        "invoice_no": None,
        "received_grv_no": None,
        "store_no": None,
        "requested_from": None,
        "project_dept": "Foundation Pouring",
        "requested_no": None,
        "siv_no": "SIV-20261105-001",
        "movement_type": "IN",
        "quantity": Decimal("15.0000"),
        "signed_quantity": Decimal("15.0000"),
        "running_balance": Decimal("315.0000"),
        "item_id": item_id,
        "item_code": "01-CM-00001",
        "item_description": "Cement Grade 42.5N",
        "category_name": "Cement & Aggregates",
        "unit": "BAG",
        "unit_price": Decimal("850.0000"),
        "warehouse_id": wh_id,
        "warehouse_code": "KZ-WH-001",
        "warehouse_name": "Kazanchis Main Warehouse",
        "project_name": "Kazanchis Commercial Complex",
        "plate_no": None,
        "driver_name": None,
        "remarks": "Surplus return against SIV",
        "entered_by_name": "Store Keeper",
    }

    service.repo.get_trial_balance = AsyncMock(
        return_value=([fake_srv_row], 1, Decimal("15.0000"), Decimal("0.0000"))
    )

    response = await service.get_trial_balance_report(
        warehouse_id=wh_id, page=1, page_size=50
    )

    assert response.total_count == 1
    assert response.total_in == Decimal("15.0000")
    assert response.total_out == Decimal("0.0000")
    srv_item = response.items[0]
    assert srv_item.transaction_type == "SRV"
    assert srv_item.in_quantity == Decimal("15.0000")
    assert srv_item.out_quantity == Decimal("0.0000")
    assert srv_item.unit_price == Decimal("850.0000")
    assert srv_item.total_price == Decimal("12750.0000")


@pytest.mark.asyncio
async def test_service_export_trial_balance_excel():
    mock_session = AsyncMock()
    service = ReportService(mock_session)

    raw_rows = [
        {
            "movement_id": uuid4(),
            "movement_date": date(2026, 9, 1),
            "created_at": datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            "transaction_id": uuid4(),
            "transaction_number": "GRV-001",
            "transaction_type": "GRV",
            "invoice_no": "INV-101",
            "received_grv_no": None,
            "siv_no": None,
            "requested_no": None,
            "istv_no": None,
            "external_reference": None,
            "item_id": uuid4(),
            "item_code": "01-CM-00001",
            "item_description": "Cement",
            "category_name": "CEMENT",
            "unit": "BAG",
            "warehouse_id": uuid4(),
            "warehouse_code": "WH001",
            "warehouse_name": "Main Warehouse",
            "project_name": "Kazanchis",
            "plate_no": None,
            "driver_name": None,
            "movement_type": "IN",
            "quantity": Decimal("100.0000"),
            "signed_quantity": Decimal("100.0000"),
            "running_balance": Decimal("100.0000"),
            "status": "POSTED",
            "entered_by_name": "Admin",
            "unit_price": Decimal("8133.0000"),
        }
    ]
    service.repo.get_all_trial_balance_movements = AsyncMock(return_value=raw_rows)

    excel_stream = await service.export_trial_balance_excel()
    assert isinstance(excel_stream, io.BytesIO)

    # Validate workbook structure
    wb = openpyxl.load_workbook(excel_stream, data_only=True)
    assert "Trial Balance" in wb.sheetnames
    ws = wb["Trial Balance"]
    assert "DETAILED INVENTORY MOVEMENT" in str(ws["A1"].value)
    # Check headers at row 4
    headers = [cell.value for cell in ws[4]]
    assert "Tx Number" in headers
    assert "Vehicle Plate No" in headers
    assert "Driver Name" in headers
    assert "IN" in headers
    assert "OUT" in headers
    assert "Unit Price (ETB)" in headers
    assert "Total Value (ETB)" in headers

    # Check data row 5
    row_5_vals = [cell.value for cell in ws[5]]
    # Column 17 is Unit Price (idx 16), Column 18 is Total Value (idx 17)
    assert row_5_vals[16] == 8133.0
    assert row_5_vals[17] == 813300.0

    # Check total row 6
    row_6_vals = [cell.value for cell in ws[6]]
    assert row_6_vals[17] == 813300.0


@pytest.mark.asyncio
async def test_service_stock_balance_available_computation():
    mock_session = AsyncMock()
    service = ReportService(mock_session)

    raw_balances = [
        {
            "warehouse_id": uuid4(),
            "warehouse_code": "WH001",
            "warehouse_name": "Main",
            "project_name": "Kazanchis",
            "category_name": "STEEL",
            "item_id": uuid4(),
            "item_code": "02-ST-00001",
            "item_description": "Rebar 12mm",
            "unit": "PCS",
            "quantity_on_hand": Decimal("500.0000"),
            "quantity_reserved": Decimal("50.0000"),
            "quantity_available": Decimal("450.0000"),
        }
    ]
    service.repo.get_current_stock_balances = AsyncMock(return_value=raw_balances)

    result = await service.get_stock_balance_report()
    assert result.total_count == 1
    assert result.items[0].quantity_available == Decimal("450.0000")
    assert result.items[0].quantity_on_hand == Decimal("500.0000")


@pytest.mark.asyncio
async def test_service_in_transit_report():
    mock_session = AsyncMock()
    service = ReportService(mock_session)

    raw_transfers = [
        {
            "transfer_record_id": uuid4(),
            "istv_transaction_id": uuid4(),
            "istv_number": "ISTV-001",
            "transaction_date": date.today(),
            "source_warehouse_name": "WH001",
            "destination_warehouse_name": "WH002",
            "plate_no": "3-A12345",
            "driver_name": "Driver A",
            "status": "IN_TRANSIT",
            "item_id": uuid4(),
            "item_code": "01-CM-00001",
            "item_description": "Cement",
            "unit": "BAG",
            "sent_quantity": Decimal("100.0000"),
            "received_quantity": Decimal("30.0000"),
            "remaining_quantity": Decimal("70.0000"),
        }
    ]
    service.repo.get_in_transit_transfers = AsyncMock(return_value=raw_transfers)

    result = await service.get_in_transit_report()
    assert len(result) == 1
    assert result[0].remaining_quantity == Decimal("70.0000")
    assert result[0].istv_number == "ISTV-001"


# ===========================================================================
# 2. API Endpoints & RBAC Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_api_trial_balance_success(token_factory):
    fake_service = FakeReportService()
    app.dependency_overrides[get_report_service] = lambda: fake_service
    token = token_factory(role="VIEWER")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/reports/trial-balance",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 1
    assert len(data["items"]) == 1
    assert Decimal(str(data["total_in"])) == Decimal("100.0000")
    assert data["items"][0]["transaction_type"] == "GRV"


@pytest.mark.asyncio
async def test_api_trial_balance_export_success(token_factory):
    fake_service = FakeReportService()
    app.dependency_overrides[get_report_service] = lambda: fake_service
    token = token_factory(role="ADMIN")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/reports/trial-balance/export",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment; filename=" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_api_stock_balances_success(token_factory):
    fake_service = FakeReportService()
    app.dependency_overrides[get_report_service] = lambda: fake_service
    token = token_factory(role="STORE_KEEPER")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/reports/stock-balances",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 1
    assert Decimal(str(data["items"][0]["quantity_available"])) == Decimal("80.0000")


@pytest.mark.asyncio
async def test_api_in_transit_success(token_factory):
    fake_service = FakeReportService()
    app.dependency_overrides[get_report_service] = lambda: fake_service
    token = token_factory(role="INVENTORY_MANAGER")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/reports/in-transit",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert Decimal(str(data[0]["remaining_quantity"])) == Decimal("40.0000")


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER", "VIEWER"])
async def test_all_authenticated_roles_can_access_reports(token_factory, role):
    fake_service = FakeReportService()
    app.dependency_overrides[get_report_service] = lambda: fake_service
    token = token_factory(role=role)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res1 = await client.get(
            "/api/v1/reports/trial-balance",
            headers={"Authorization": f"Bearer {token}"},
        )
        res2 = await client.get(
            "/api/v1/reports/stock-balances",
            headers={"Authorization": f"Bearer {token}"},
        )
        res3 = await client.get(
            "/api/v1/reports/in-transit",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res3.status_code == 200


@pytest.mark.asyncio
async def test_reports_unauthenticated_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res1 = await client.get("/api/v1/reports/trial-balance")
        res2 = await client.get("/api/v1/reports/trial-balance/export")
        res3 = await client.get("/api/v1/reports/stock-balances")
        res4 = await client.get("/api/v1/reports/in-transit")

    assert res1.status_code in (401, 403)
    assert res2.status_code in (401, 403)
    assert res3.status_code in (401, 403)
    assert res4.status_code in (401, 403)

@pytest.mark.asyncio
async def test_service_trial_balance_renders_adjustment_quantity_unit_price_and_total_value():
    """Confirms ADJUSTMENT movements render quantity, unit_price, and calculated total_price in Trial Balance."""
    mock_session = AsyncMock()
    service = ReportService(mock_session)
    wh_id = uuid4()
    item_id = uuid4()

    fake_adj_in_row = {
        "movement_id": uuid4(),
        "movement_date": date.today(),
        "created_at": datetime.now(timezone.utc),
        "transaction_id": uuid4(),
        "transaction_number": "ADJ-20261105-0001",
        "transaction_type": "ADJUSTMENT",
        "external_reference": None,
        "supplier_name": None,
        "invoice_no": None,
        "received_grv_no": None,
        "store_no": None,
        "requested_from": None,
        "project_dept": None,
        "requested_no": None,
        "siv_no": None,
        "movement_type": "IN",
        "quantity": Decimal("10.0000"),
        "signed_quantity": Decimal("10.0000"),
        "running_balance": Decimal("110.0000"),
        "item_id": item_id,
        "item_code": "01-CM-00001",
        "item_description": "Cement Grade 42.5N",
        "category_name": "Cement & Aggregates",
        "unit": "BAG",
        "unit_price": Decimal("850.0000"),
        "warehouse_id": wh_id,
        "warehouse_code": "KZ-WH-001",
        "warehouse_name": "Kazanchis Main Warehouse",
        "project_name": None,
        "plate_no": None,
        "driver_name": None,
        "remarks": "Physical surplus count adjustment",
        "entered_by_name": "Inventory Manager",
    }

    fake_adj_out_row = {
        "movement_id": uuid4(),
        "movement_date": date.today(),
        "created_at": datetime.now(timezone.utc),
        "transaction_id": uuid4(),
        "transaction_number": "ADJ-20261105-0002",
        "transaction_type": "ADJUSTMENT",
        "external_reference": None,
        "supplier_name": None,
        "invoice_no": None,
        "received_grv_no": None,
        "store_no": None,
        "requested_from": None,
        "project_dept": None,
        "requested_no": None,
        "siv_no": None,
        "movement_type": "OUT",
        "quantity": Decimal("4.0000"),
        "signed_quantity": Decimal("-4.0000"),
        "running_balance": Decimal("106.0000"),
        "item_id": item_id,
        "item_code": "01-CM-00001",
        "item_description": "Cement Grade 42.5N",
        "category_name": "Cement & Aggregates",
        "unit": "BAG",
        "unit_price": Decimal("850.0000"),
        "warehouse_id": wh_id,
        "warehouse_code": "KZ-WH-001",
        "warehouse_name": "Kazanchis Main Warehouse",
        "project_name": None,
        "plate_no": None,
        "driver_name": None,
        "remarks": "Damaged cement write-off",
        "entered_by_name": "Inventory Manager",
    }

    service.repo.get_trial_balance = AsyncMock(
        return_value=([fake_adj_in_row, fake_adj_out_row], 2, Decimal("10.0000"), Decimal("4.0000"))
    )

    response = await service.get_trial_balance_report(
        warehouse_id=wh_id, page=1, page_size=50
    )

    assert response.total_count == 2
    assert response.total_in == Decimal("10.0000")
    assert response.total_out == Decimal("4.0000")
    item_in = response.items[0]
    assert item_in.transaction_type == "ADJUSTMENT"
    assert item_in.in_quantity == Decimal("10.0000")
    assert item_in.out_quantity == Decimal("0.0000")
    assert item_in.unit_price == Decimal("850.0000")
    assert item_in.total_price == Decimal("8500.0000")

    item_out = response.items[1]
    assert item_out.transaction_type == "ADJUSTMENT"
    assert item_out.in_quantity == Decimal("0.0000")
    assert item_out.out_quantity == Decimal("4.0000")
    assert item_out.unit_price == Decimal("850.0000")
    assert item_out.total_price == Decimal("3400.0000")


@pytest.mark.asyncio
async def test_service_trial_balance_moving_wac_and_remaining_value():
    """
    Verifies chronological Moving Weighted Average Cost (WAC):
    10 @ 100 ETB + 10 @ 200 ETB -> WAC = 150 ETB
    Issue 5 -> Remaining Qty = 15, WAC = 150 ETB, Remaining Value = 2,250.00 ETB.
    """
    mock_session = AsyncMock()
    service = ReportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    base_dt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)

    mov1 = {
        "movement_id": uuid4(),
        "movement_date": date(2026, 9, 1),
        "created_at": base_dt,
        "transaction_id": uuid4(),
        "transaction_number": "GRV-001",
        "transaction_type": "GRV",
        "invoice_no": "INV-001",
        "item_id": item_id,
        "item_code": "01-CM-00001",
        "item_description": "Portland Cement",
        "category_name": "CEMENT",
        "unit": "BAG",
        "warehouse_id": wh_id,
        "warehouse_code": "WH001",
        "warehouse_name": "Main Warehouse",
        "project_name": "Kazanchis",
        "movement_type": "IN",
        "quantity": Decimal("10.0000"),
        "signed_quantity": Decimal("10.0000"),
        "running_balance": Decimal("10.0000"),
        "status": "POSTED",
        "entered_by_name": "Clerk",
        "unit_price": Decimal("100.0000"),
    }
    mov2 = {
        "movement_id": uuid4(),
        "movement_date": date(2026, 9, 2),
        "created_at": base_dt + timedelta(days=1),
        "transaction_id": uuid4(),
        "transaction_number": "GRV-002",
        "transaction_type": "GRV",
        "invoice_no": "INV-002",
        "item_id": item_id,
        "item_code": "01-CM-00001",
        "item_description": "Portland Cement",
        "category_name": "CEMENT",
        "unit": "BAG",
        "warehouse_id": wh_id,
        "warehouse_code": "WH001",
        "warehouse_name": "Main Warehouse",
        "project_name": "Kazanchis",
        "movement_type": "IN",
        "quantity": Decimal("10.0000"),
        "signed_quantity": Decimal("10.0000"),
        "running_balance": Decimal("20.0000"),
        "status": "POSTED",
        "entered_by_name": "Clerk",
        "unit_price": Decimal("200.0000"),
    }
    mov3 = {
        "movement_id": uuid4(),
        "movement_date": date(2026, 9, 3),
        "created_at": base_dt + timedelta(days=2),
        "transaction_id": uuid4(),
        "transaction_number": "SIV-001",
        "transaction_type": "SIV",
        "siv_no": "SIV-101",
        "item_id": item_id,
        "item_code": "01-CM-00001",
        "item_description": "Portland Cement",
        "category_name": "CEMENT",
        "unit": "BAG",
        "warehouse_id": wh_id,
        "warehouse_code": "WH001",
        "warehouse_name": "Main Warehouse",
        "project_name": "Kazanchis",
        "movement_type": "OUT",
        "quantity": Decimal("5.0000"),
        "signed_quantity": Decimal("-5.0000"),
        "running_balance": Decimal("15.0000"),
        "status": "POSTED",
        "entered_by_name": "Clerk",
        "unit_price": Decimal("150.0000"),
    }

    desc_rows = [mov3, mov2, mov1]
    service.repo.get_trial_balance = AsyncMock(
        return_value=(desc_rows, 3, Decimal("20.0000"), Decimal("5.0000"))
    )
    service.repo.get_all_trial_balance_movements = AsyncMock(return_value=desc_rows)

    res = await service.get_trial_balance_report(page=1, page_size=50)

    # Order returned matches DESC ledger order: [mov3, mov2, mov1]
    assert res.items[0].running_balance == Decimal("15.0000")
    assert res.items[0].weighted_avg_unit_price == Decimal("150.0000")
    assert res.items[0].remaining_value == Decimal("2250.00")

    assert res.items[1].running_balance == Decimal("20.0000")
    assert res.items[1].weighted_avg_unit_price == Decimal("150.0000")
    assert res.items[1].remaining_value == Decimal("3000.00")

    assert res.items[2].running_balance == Decimal("10.0000")
    assert res.items[2].weighted_avg_unit_price == Decimal("100.0000")
    assert res.items[2].remaining_value == Decimal("1000.00")

    # Summary has 1 deduplicated row and exact grand totals
    assert len(res.remaining_summary) == 1
    summary_row = res.remaining_summary[0]
    assert summary_row.total_in == Decimal("20.0000")
    assert summary_row.total_out == Decimal("5.0000")
    assert summary_row.remaining_qty == Decimal("15.0000")
    assert summary_row.weighted_avg_unit_price == Decimal("150.0000")
    assert summary_row.remaining_value == Decimal("2250.00")
    assert res.total_remaining_qty == Decimal("15.0000")
    assert res.total_remaining_value == Decimal("2250.00")


@pytest.mark.asyncio
async def test_service_trial_balance_pagination_preserves_chronological_wac():
    """Ensures page slicing does not skew weighted_avg_unit_price or remaining_value."""
    mock_session = AsyncMock()
    service = ReportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    base_dt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)

    mov1 = {
        "movement_id": uuid4(),
        "movement_date": date(2026, 9, 1),
        "created_at": base_dt,
        "transaction_id": uuid4(),
        "transaction_number": "GRV-001",
        "transaction_type": "GRV",
        "item_id": item_id,
        "item_code": "01-CM-00001",
        "item_description": "Cement",
        "category_name": "CEMENT",
        "unit": "BAG",
        "warehouse_id": wh_id,
        "warehouse_code": "WH001",
        "warehouse_name": "Main WH",
        "movement_type": "IN",
        "quantity": Decimal("10.0000"),
        "signed_quantity": Decimal("10.0000"),
        "running_balance": Decimal("10.0000"),
        "status": "POSTED",
        "entered_by_name": "Admin",
        "unit_price": Decimal("100.0000"),
    }
    mov2 = {
        "movement_id": uuid4(),
        "movement_date": date(2026, 9, 2),
        "created_at": base_dt + timedelta(days=1),
        "transaction_id": uuid4(),
        "transaction_number": "GRV-002",
        "transaction_type": "GRV",
        "item_id": item_id,
        "item_code": "01-CM-00001",
        "item_description": "Cement",
        "category_name": "CEMENT",
        "unit": "BAG",
        "warehouse_id": wh_id,
        "warehouse_code": "WH001",
        "warehouse_name": "Main WH",
        "movement_type": "IN",
        "quantity": Decimal("10.0000"),
        "signed_quantity": Decimal("10.0000"),
        "running_balance": Decimal("20.0000"),
        "status": "POSTED",
        "entered_by_name": "Admin",
        "unit_price": Decimal("200.0000"),
    }
    mov3 = {
        "movement_id": uuid4(),
        "movement_date": date(2026, 9, 3),
        "created_at": base_dt + timedelta(days=2),
        "transaction_id": uuid4(),
        "transaction_number": "SIV-001",
        "transaction_type": "SIV",
        "item_id": item_id,
        "item_code": "01-CM-00001",
        "item_description": "Cement",
        "category_name": "CEMENT",
        "unit": "BAG",
        "warehouse_id": wh_id,
        "warehouse_code": "WH001",
        "warehouse_name": "Main WH",
        "movement_type": "OUT",
        "quantity": Decimal("5.0000"),
        "signed_quantity": Decimal("-5.0000"),
        "running_balance": Decimal("15.0000"),
        "status": "POSTED",
        "entered_by_name": "Admin",
        "unit_price": None,
    }

    # Page 2 with page_size=1 returns only mov2
    service.repo.get_trial_balance = AsyncMock(
        return_value=([mov2], 3, Decimal("20.0000"), Decimal("5.0000"))
    )
    service.repo.get_all_trial_balance_movements = AsyncMock(
        return_value=[mov3, mov2, mov1]
    )

    res = await service.get_trial_balance_report(page=2, page_size=1)
    assert len(res.items) == 1
    assert res.items[0].transaction_number == "GRV-002"
    # WAC reflects mov1 (10@100) + mov2 (10@200) = 150, NOT 200
    assert res.items[0].weighted_avg_unit_price == Decimal("150.0000")
    assert res.items[0].remaining_value == Decimal("3000.00")
    assert res.total_remaining_qty == Decimal("15.0000")
    assert res.total_remaining_value == Decimal("2250.00")


@pytest.mark.asyncio
async def test_service_trial_balance_unpriced_and_no_double_counting_totals():
    """
    Verifies unpriced items yield None for WAC/remaining_value without crashing,
    and Remaining Stock Summary grand totals do not double-count items with multiple movements.
    """
    mock_session = AsyncMock()
    service = ReportService(mock_session)

    wh_id = uuid4()
    item_priced = uuid4()
    item_unpriced = uuid4()
    base_dt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)

    raw_rows = [
        # Item 1 (priced, 2 movements): 10 @ 50 IN, then 2 OUT -> remaining 8 @ 50 = 400.00
        {
            "movement_id": uuid4(),
            "movement_date": date(2026, 9, 2),
            "created_at": base_dt + timedelta(hours=2),
            "transaction_id": uuid4(),
            "transaction_number": "SIV-010",
            "transaction_type": "SIV",
            "item_id": item_priced,
            "item_code": "01-CM-00001",
            "item_description": "Cement",
            "category_name": "CEMENT",
            "unit": "BAG",
            "warehouse_id": wh_id,
            "warehouse_code": "WH001",
            "warehouse_name": "Main WH",
            "movement_type": "OUT",
            "quantity": Decimal("2.0000"),
            "signed_quantity": Decimal("-2.0000"),
            "running_balance": Decimal("8.0000"),
            "status": "POSTED",
            "entered_by_name": "Admin",
            "unit_price": None,
        },
        {
            "movement_id": uuid4(),
            "movement_date": date(2026, 9, 1),
            "created_at": base_dt,
            "transaction_id": uuid4(),
            "transaction_number": "GRV-010",
            "transaction_type": "GRV",
            "item_id": item_priced,
            "item_code": "01-CM-00001",
            "item_description": "Cement",
            "category_name": "CEMENT",
            "unit": "BAG",
            "warehouse_id": wh_id,
            "warehouse_code": "WH001",
            "warehouse_name": "Main WH",
            "movement_type": "IN",
            "quantity": Decimal("10.0000"),
            "signed_quantity": Decimal("10.0000"),
            "running_balance": Decimal("10.0000"),
            "status": "POSTED",
            "entered_by_name": "Admin",
            "unit_price": Decimal("50.0000"),
        },
        # Item 2 (unpriced, 2 movements): 12 IN (None price), 4 OUT -> remaining 8, WAC None
        {
            "movement_id": uuid4(),
            "movement_date": date(2026, 9, 2),
            "created_at": base_dt + timedelta(hours=3),
            "transaction_id": uuid4(),
            "transaction_number": "SIV-011",
            "transaction_type": "SIV",
            "item_id": item_unpriced,
            "item_code": "02-ST-00001",
            "item_description": "Unpriced Rebar",
            "category_name": "STEEL",
            "unit": "PCS",
            "warehouse_id": wh_id,
            "warehouse_code": "WH001",
            "warehouse_name": "Main WH",
            "movement_type": "OUT",
            "quantity": Decimal("4.0000"),
            "signed_quantity": Decimal("-4.0000"),
            "running_balance": Decimal("8.0000"),
            "status": "POSTED",
            "entered_by_name": "Admin",
            "unit_price": None,
        },
        {
            "movement_id": uuid4(),
            "movement_date": date(2026, 9, 1),
            "created_at": base_dt + timedelta(hours=1),
            "transaction_id": uuid4(),
            "transaction_number": "GRV-011",
            "transaction_type": "GRV",
            "item_id": item_unpriced,
            "item_code": "02-ST-00001",
            "item_description": "Unpriced Rebar",
            "category_name": "STEEL",
            "unit": "PCS",
            "warehouse_id": wh_id,
            "warehouse_code": "WH001",
            "warehouse_name": "Main WH",
            "movement_type": "IN",
            "quantity": Decimal("12.0000"),
            "signed_quantity": Decimal("12.0000"),
            "running_balance": Decimal("12.0000"),
            "status": "POSTED",
            "entered_by_name": "Admin",
            "unit_price": None,
        },
    ]

    service.repo.get_trial_balance = AsyncMock(
        return_value=(raw_rows, 4, Decimal("22.0000"), Decimal("6.0000"))
    )
    service.repo.get_all_trial_balance_movements = AsyncMock(return_value=raw_rows)

    res = await service.get_trial_balance_report(page=1, page_size=50)

    assert len(res.remaining_summary) == 2
    by_code = {s.item_code: s for s in res.remaining_summary}
    assert by_code["01-CM-00001"].remaining_qty == Decimal("8.0000")
    assert by_code["01-CM-00001"].weighted_avg_unit_price == Decimal("50.0000")
    assert by_code["01-CM-00001"].remaining_value == Decimal("400.00")

    assert by_code["02-ST-00001"].remaining_qty == Decimal("8.0000")
    assert by_code["02-ST-00001"].weighted_avg_unit_price is None
    assert by_code["02-ST-00001"].remaining_value is None

    # Grand totals sum distinct (WH, Item) remaining quantities: 8 + 8 = 16 (not 8+10+8+12=38)
    assert res.total_remaining_qty == Decimal("16.0000")
    assert res.total_remaining_value == Decimal("400.00")


@pytest.mark.asyncio
async def test_service_export_trial_balance_excel_two_sheets_and_summary_totals():
    """Verifies exported .xlsx contains both 'Trial Balance' and 'Remaining Stock Summary' sheets with accurate totals."""
    mock_session = AsyncMock()
    service = ReportService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    base_dt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)

    raw_rows = [
        {
            "movement_id": uuid4(),
            "movement_date": date(2026, 9, 3),
            "created_at": base_dt + timedelta(days=2),
            "transaction_id": uuid4(),
            "transaction_number": "SIV-001",
            "transaction_type": "SIV",
            "siv_no": "SIV-101",
            "item_id": item_id,
            "item_code": "01-CM-00001",
            "item_description": "Portland Cement",
            "category_name": "CEMENT",
            "unit": "BAG",
            "warehouse_id": wh_id,
            "warehouse_code": "WH001",
            "warehouse_name": "Main Warehouse",
            "project_name": "Kazanchis",
            "movement_type": "OUT",
            "quantity": Decimal("5.0000"),
            "signed_quantity": Decimal("-5.0000"),
            "running_balance": Decimal("15.0000"),
            "status": "POSTED",
            "entered_by_name": "Store Keeper",
            "unit_price": Decimal("150.0000"),
        },
        {
            "movement_id": uuid4(),
            "movement_date": date(2026, 9, 2),
            "created_at": base_dt + timedelta(days=1),
            "transaction_id": uuid4(),
            "transaction_number": "GRV-002",
            "transaction_type": "GRV",
            "invoice_no": "INV-002",
            "item_id": item_id,
            "item_code": "01-CM-00001",
            "item_description": "Portland Cement",
            "category_name": "CEMENT",
            "unit": "BAG",
            "warehouse_id": wh_id,
            "warehouse_code": "WH001",
            "warehouse_name": "Main Warehouse",
            "project_name": "Kazanchis",
            "movement_type": "IN",
            "quantity": Decimal("10.0000"),
            "signed_quantity": Decimal("10.0000"),
            "running_balance": Decimal("20.0000"),
            "status": "POSTED",
            "entered_by_name": "Store Keeper",
            "unit_price": Decimal("200.0000"),
        },
        {
            "movement_id": uuid4(),
            "movement_date": date(2026, 9, 1),
            "created_at": base_dt,
            "transaction_id": uuid4(),
            "transaction_number": "GRV-001",
            "transaction_type": "GRV",
            "invoice_no": "INV-001",
            "item_id": item_id,
            "item_code": "01-CM-00001",
            "item_description": "Portland Cement",
            "category_name": "CEMENT",
            "unit": "BAG",
            "warehouse_id": wh_id,
            "warehouse_code": "WH001",
            "warehouse_name": "Main Warehouse",
            "project_name": "Kazanchis",
            "movement_type": "IN",
            "quantity": Decimal("10.0000"),
            "signed_quantity": Decimal("10.0000"),
            "running_balance": Decimal("10.0000"),
            "status": "POSTED",
            "entered_by_name": "Store Keeper",
            "unit_price": Decimal("100.0000"),
        },
    ]
    service.repo.get_all_trial_balance_movements = AsyncMock(return_value=raw_rows)

    excel_stream = await service.export_trial_balance_excel()
    wb = openpyxl.load_workbook(excel_stream, data_only=True)

    assert wb.sheetnames == ["Trial Balance", "Remaining Stock Summary"]

    # Sheet 1 verification
    ws1 = wb["Trial Balance"]
    s1_headers = [cell.value for cell in ws1[4]]
    assert "Remaining Qty" in s1_headers
    assert "Running Bal" not in s1_headers
    assert "Weighted Avg Price (ETB)" in s1_headers
    assert "Remaining Value (ETB)" in s1_headers

    # Row 5 is SIV-001 (idx 18 = WAC 150.0, idx 19 = Remaining Value 2250.0)
    s1_row5 = [cell.value for cell in ws1[5]]
    assert s1_row5[15] == 15.0
    assert s1_row5[18] == 150.0
    assert s1_row5[19] == 2250.0

    # Sheet 1 TOTAL row (row 8): IN=20, OUT=5, Total Value=3750, Remaining Qty & Value blank
    s1_total = [cell.value for cell in ws1[8]]
    assert s1_total[13] == 20.0
    assert s1_total[14] == 5.0
    assert s1_total[15] in ("", None)
    assert s1_total[17] == 3750.0
    assert s1_total[19] in ("", None)

    # Sheet 2 verification
    ws2 = wb["Remaining Stock Summary"]
    s2_headers = [cell.value for cell in ws2[4]]
    assert s2_headers == [
        "Item Code",
        "Description",
        "Category",
        "Unit",
        "WH Code",
        "Warehouse Name",
        "Project",
        "Total IN",
        "Total OUT",
        "Remaining Qty",
        "Weighted Avg Price (ETB)",
        "Remaining Value (ETB)",
    ]

    # Data row 5 (1 deduplicated row)
    s2_row5 = [cell.value for cell in ws2[5]]
    assert s2_row5[0] == "01-CM-00001"
    assert s2_row5[7] == 20.0
    assert s2_row5[8] == 5.0
    assert s2_row5[9] == 15.0
    assert s2_row5[10] == 150.0
    assert s2_row5[11] == 2250.0

    # TOTAL row 6
    s2_total = [cell.value for cell in ws2[6]]
    assert s2_total[0] == "TOTAL"
    assert s2_total[7] == 20.0
    assert s2_total[8] == 5.0
    assert s2_total[9] == 15.0
    assert s2_total[11] == 2250.0
