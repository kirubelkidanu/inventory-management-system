# backend/tests/test_physical_count_reconciliation.py
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt
import pytest

from app.api.routes.reconciliation import get_reconciliation_service
from app.core.config import settings
from app.main import app
from app.models.category import Category
from app.models.inventory import InventoryBalance
from app.models.item import Item
from app.models.transaction import Transaction, TransactionLine
from app.models.warehouse import Warehouse
from app.schemas.reconciliation import (
    CountSheetItem,
    CountSheetResponse,
    PhysicalCountItemInput,
    PhysicalCountSubmitRequest,
    ReconciliationCommitRequest,
    ReconciliationPreviewResponse,
    VarianceItem,
)
from app.services.reconciliation import ReconciliationService, _to_uuid


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


class FakeReconciliationService:
    def __init__(self):
        self.count_sheet_calls = []
        self.preview_calls = []
        self.commit_calls = []

    async def generate_count_sheet(self, warehouse_id):
        self.count_sheet_calls.append(warehouse_id)
        return CountSheetResponse(
            warehouse_id=warehouse_id,
            warehouse_code="WH-MAIN",
            warehouse_name="Main Warehouse",
            generated_at=datetime.now(timezone.utc),
            total_items=1,
            items=[
                CountSheetItem(
                    item_id=uuid4(),
                    item_code="01-CM-00001",
                    item_description="Portland Cement",
                    category_name="CEMENT",
                    unit="BAG",
                    system_quantity_on_hand=Decimal("100.0000"),
                )
            ],
        )

    async def calculate_variance_preview(self, payload):
        self.preview_calls.append(payload)
        return ReconciliationPreviewResponse(
            warehouse_id=payload.warehouse_id,
            warehouse_code="WH-MAIN",
            warehouse_name="Main Warehouse",
            count_date=payload.count_date,
            count_reference=payload.count_reference,
            total_items_counted=len(payload.counts),
            matched_items_count=1,
            surplus_items_count=0,
            deficit_items_count=0,
            variances=[
                VarianceItem(
                    item_id=payload.counts[0].item_id,
                    item_code="01-CM-00001",
                    item_description="Portland Cement",
                    unit="BAG",
                    system_quantity=Decimal("100.0000"),
                    counted_quantity=Decimal("100.0000"),
                    variance_quantity=Decimal("0.0000"),
                    adjustment_direction="NONE",
                    remarks=None,
                )
            ],
        )

    async def commit_reconciliation_adjustments(self, user_id, payload):
        self.commit_calls.append((user_id, payload))
        return {
            "message": "Physical count reconciliation adjustments posted successfully.",
            "count_reference": payload.count_reference,
            "transaction_id": str(uuid4()),
            "transaction_number": "ADJ-20260918-ABCD1234",
            "adjusted_lines_count": len(payload.counts),
            "warehouse_id": str(payload.warehouse_id),
        }


# ==============================================================================
# Service Unit Tests: Count Sheet, Variance Calculation, and Commit
# ==============================================================================


@pytest.mark.asyncio
async def test_service_generate_count_sheet_success():
    mock_session = AsyncMock()
    service = ReconciliationService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)

    # First query checks warehouse existence
    mock_wh_res = MagicMock()
    mock_wh_res.scalar_one_or_none.return_value = wh

    # Second query returns items join with balance
    mock_row = MagicMock()
    mock_row.item_id = item_id
    mock_row.item_code = "01-CM-00001"
    mock_row.item_description = "Portland Cement"
    mock_row.category_name = "CEMENT"
    mock_row.unit = "BAG"
    mock_row.system_quantity_on_hand = Decimal("150.0000")

    mock_items_res = MagicMock()
    mock_items_res.all.return_value = [mock_row]

    mock_session.execute = AsyncMock(side_effect=[mock_wh_res, mock_items_res])

    response = await service.generate_count_sheet(warehouse_id=wh_id)

    assert response.warehouse_id == wh_id
    assert response.warehouse_code == "WH-001"
    assert response.total_items == 1
    assert response.items[0].item_id == item_id
    assert response.items[0].item_code == "01-CM-00001"
    assert response.items[0].system_quantity_on_hand == Decimal("150.0000")


@pytest.mark.asyncio
async def test_service_generate_count_sheet_warehouse_not_found():
    mock_session = AsyncMock()
    service = ReconciliationService(mock_session)

    mock_wh_res = MagicMock()
    mock_wh_res.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_wh_res)

    with pytest.raises(HTTPException) as exc:
        await service.generate_count_sheet(warehouse_id=uuid4())

    assert exc.value.status_code == 404
    assert "not found" in exc.value.detail


@pytest.mark.asyncio
async def test_service_calculate_variance_preview():
    mock_session = AsyncMock()
    service = ReconciliationService(mock_session)

    wh_id = uuid4()
    item1_id = uuid4()
    item2_id = uuid4()
    item3_id = uuid4()

    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item1 = Item(id=item1_id, item_code="01-CM-00001", description="Cement 1", default_unit="BAG", is_active=True)
    item2 = Item(id=item2_id, item_code="01-CM-00002", description="Cement 2", default_unit="BAG", is_active=True)
    item3 = Item(id=item3_id, item_code="01-CM-00003", description="Cement 3", default_unit="BAG", is_active=True)

    bal1 = InventoryBalance(id=uuid4(), warehouse_id=wh_id, item_id=item1_id, quantity_on_hand=Decimal("10.0000"))
    bal2 = InventoryBalance(id=uuid4(), warehouse_id=wh_id, item_id=item2_id, quantity_on_hand=Decimal("20.0000"))
    bal3 = InventoryBalance(id=uuid4(), warehouse_id=wh_id, item_id=item3_id, quantity_on_hand=Decimal("30.0000"))

    # Mock execute results
    mock_wh_res = MagicMock()
    mock_wh_res.scalar_one_or_none.return_value = wh

    mock_items_res = MagicMock()
    mock_items_res.scalars.return_value.all.return_value = [item1, item2, item3]

    mock_bal_res = MagicMock()
    mock_bal_res.scalars.return_value.all.return_value = [bal1, bal2, bal3]

    mock_session.execute = AsyncMock(side_effect=[mock_wh_res, mock_items_res, mock_bal_res])

    # Item 1: system=10, counted=15 -> Surplus (IN), +5
    # Item 2: system=20, counted=12 -> Deficit (OUT), -8
    # Item 3: system=30, counted=30 -> Matched (NONE), 0
    payload = PhysicalCountSubmitRequest(
        warehouse_id=wh_id,
        count_date=date.today(),
        count_reference="Q3-COUNT-01",
        counts=[
            PhysicalCountItemInput(item_id=item1_id, counted_quantity=Decimal("15.0000")),
            PhysicalCountItemInput(item_id=item2_id, counted_quantity=Decimal("12.0000")),
            PhysicalCountItemInput(item_id=item3_id, counted_quantity=Decimal("30.0000")),
        ],
    )

    preview = await service.calculate_variance_preview(payload=payload)

    assert preview.total_items_counted == 3
    assert preview.surplus_items_count == 1
    assert preview.deficit_items_count == 1
    assert preview.matched_items_count == 1

    var1 = next(v for v in preview.variances if v.item_id == item1_id)
    assert var1.adjustment_direction == "IN"
    assert var1.variance_quantity == Decimal("5.0000")
    assert var1.system_quantity == Decimal("10.0000")
    assert var1.counted_quantity == Decimal("15.0000")

    var2 = next(v for v in preview.variances if v.item_id == item2_id)
    assert var2.adjustment_direction == "OUT"
    assert var2.variance_quantity == Decimal("8.0000")
    assert var2.system_quantity == Decimal("20.0000")
    assert var2.counted_quantity == Decimal("12.0000")

    var3 = next(v for v in preview.variances if v.item_id == item3_id)
    assert var3.adjustment_direction == "NONE"
    assert var3.variance_quantity == Decimal("0.0000")


@pytest.mark.asyncio
async def test_service_commit_reconciliation_adjustments_success():
    mock_session = AsyncMock()
    service = ReconciliationService(mock_session)

    wh_id = uuid4()
    item1_id = uuid4()
    item2_id = uuid4()
    user_id = uuid4()

    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item1 = Item(id=item1_id, item_code="01-CM-00001", description="Cement 1", default_unit="BAG", is_active=True)
    item2 = Item(id=item2_id, item_code="01-CM-00002", description="Cement 2", default_unit="BAG", is_active=True)

    bal1 = InventoryBalance(
        id=uuid4(), warehouse_id=wh_id, item_id=item1_id,
        quantity_on_hand=Decimal("10.0000"), quantity_reserved=Decimal("0.0000")
    )
    bal2 = InventoryBalance(
        id=uuid4(), warehouse_id=wh_id, item_id=item2_id,
        quantity_on_hand=Decimal("20.0000"), quantity_reserved=Decimal("0.0000")
    )

    mock_wh_res = MagicMock()
    mock_wh_res.scalar_one_or_none.return_value = wh

    mock_items_res = MagicMock()
    mock_items_res.scalars.return_value.all.return_value = [item1, item2]

    mock_session.execute = AsyncMock(side_effect=[mock_wh_res, mock_items_res])

    # Mock tx_repo and tx_service
    service.tx_repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item1_id: bal1, item2_id: bal2}
    )
    service.tx_repo.create_audit_log = AsyncMock()

    mock_tx = Transaction(
        id=uuid4(),
        transaction_number="ADJ-20260918-12345678",
        transaction_type="ADJUSTMENT",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=wh_id,
    )
    service.tx_service.create_and_post_adjustment = AsyncMock(return_value=mock_tx)

    # Item 1: system=10, counted=14 -> Surplus +4 IN
    # Item 2: system=20, counted=17 -> Deficit -3 OUT
    payload = ReconciliationCommitRequest(
        warehouse_id=wh_id,
        count_date=date.today(),
        count_reference="Q3-COUNT-WH001",
        adjustment_reason="Physical inventory count audit variance adjustment",
        counts=[
            PhysicalCountItemInput(item_id=item1_id, counted_quantity=Decimal("14.0000")),
            PhysicalCountItemInput(item_id=item2_id, counted_quantity=Decimal("17.0000")),
        ],
    )

    result = await service.commit_reconciliation_adjustments(user_id=user_id, payload=payload)

    assert result["count_reference"] == "Q3-COUNT-WH001"
    assert result["transaction_id"] == str(mock_tx.id)
    assert result["transaction_number"] == "ADJ-20260918-12345678"
    assert result["adjusted_lines_count"] == 2

    # Verify create_and_post_adjustment was called with 2 lines
    service.tx_service.create_and_post_adjustment.assert_called_once()
    adj_call_payload = service.tx_service.create_and_post_adjustment.call_args[1]["payload"]
    assert len(adj_call_payload.lines) == 2

    line_in = next(l for l in adj_call_payload.lines if l.item_id == item1_id)
    assert line_in.direction == "IN"
    assert line_in.quantity == Decimal("4.0000")

    line_out = next(l for l in adj_call_payload.lines if l.item_id == item2_id)
    assert line_out.direction == "OUT"
    assert line_out.quantity == Decimal("3.0000")

    # Verify audit log recorded
    service.tx_repo.create_audit_log.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_service_commit_reconciliation_zero_variance_no_adjustment():
    mock_session = AsyncMock()
    service = ReconciliationService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    wh = Warehouse(id=wh_id, code="WH-001", name="Main Warehouse", is_active=True)
    item = Item(id=item_id, item_code="01-CM-00001", description="Cement 1", default_unit="BAG", is_active=True)

    bal = InventoryBalance(
        id=uuid4(), warehouse_id=wh_id, item_id=item_id,
        quantity_on_hand=Decimal("50.0000"), quantity_reserved=Decimal("0.0000")
    )

    mock_wh_res = MagicMock()
    mock_wh_res.scalar_one_or_none.return_value = wh

    mock_items_res = MagicMock()
    mock_items_res.scalars.return_value.all.return_value = [item]

    mock_session.execute = AsyncMock(side_effect=[mock_wh_res, mock_items_res])
    service.tx_repo.lock_inventory_balances_for_update = AsyncMock(return_value={item_id: bal})
    service.tx_service.create_and_post_adjustment = AsyncMock()

    payload = ReconciliationCommitRequest(
        warehouse_id=wh_id,
        count_date=date.today(),
        count_reference="Q3-COUNT-MATCH",
        adjustment_reason="Physical count reconciliation",
        counts=[
            PhysicalCountItemInput(item_id=item_id, counted_quantity=Decimal("50.0000")),
        ],
    )

    result = await service.commit_reconciliation_adjustments(user_id=uuid4(), payload=payload)

    assert "No adjustments needed" in result["message"]
    assert result["transaction_id"] is None
    assert result["transaction_number"] is None
    assert result["adjusted_lines_count"] == 0
    service.tx_service.create_and_post_adjustment.assert_not_called()


# ==============================================================================
# Pydantic Validation Tests
# ==============================================================================


def test_schema_rejects_negative_counted_quantity():
    with pytest.raises(Exception):
        PhysicalCountItemInput(
            item_id=uuid4(),
            counted_quantity=Decimal("-1.0000"),
        )


def test_schema_rejects_duplicate_items_in_count():
    item_id = uuid4()
    with pytest.raises(Exception) as exc:
        PhysicalCountSubmitRequest(
            warehouse_id=uuid4(),
            count_reference="REF-01",
            counts=[
                PhysicalCountItemInput(item_id=item_id, counted_quantity=Decimal("10")),
                PhysicalCountItemInput(item_id=item_id, counted_quantity=Decimal("20")),
            ],
        )
    assert "Duplicate item in count lines" in str(exc.value)


def test_schema_rejects_empty_adjustment_reason():
    with pytest.raises(Exception) as exc:
        ReconciliationCommitRequest(
            warehouse_id=uuid4(),
            count_reference="REF-01",
            adjustment_reason="   ",
            counts=[
                PhysicalCountItemInput(item_id=uuid4(), counted_quantity=Decimal("10")),
            ],
        )
    assert "Adjustment reason cannot be empty" in str(exc.value)


# ==============================================================================
# REST API & RBAC Authorization Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_api_get_count_sheet_store_keeper_authorized(token_factory):
    fake_service = FakeReconciliationService()
    app.dependency_overrides[get_reconciliation_service] = lambda: fake_service

    # STORE_KEEPER is allowed to view count sheets
    token = token_factory(role="STORE_KEEPER")
    wh_id = uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/reconciliation/count-sheet/{wh_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["warehouse_code"] == "WH-MAIN"
    assert len(data["items"]) == 1
    assert data["items"][0]["item_code"] == "01-CM-00001"


@pytest.mark.asyncio
async def test_api_preview_variance_admin_success(token_factory):
    fake_service = FakeReconciliationService()
    app.dependency_overrides[get_reconciliation_service] = lambda: fake_service

    token = token_factory(role="ADMIN")
    wh_id = uuid4()
    item_id = uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/reconciliation/preview",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "warehouse_id": str(wh_id),
                "count_date": str(date.today()),
                "count_reference": "Q3-PREVIEW-01",
                "counts": [{"item_id": str(item_id), "counted_quantity": "100.0000"}],
            },
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["count_reference"] == "Q3-PREVIEW-01"
    assert data["total_items_counted"] == 1
    assert len(fake_service.preview_calls) == 1


@pytest.mark.asyncio
async def test_api_commit_reconciliation_inventory_manager_success(token_factory):
    fake_service = FakeReconciliationService()
    app.dependency_overrides[get_reconciliation_service] = lambda: fake_service

    token = token_factory(role="INVENTORY_MANAGER")
    wh_id = uuid4()
    item_id = uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/reconciliation/commit",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "warehouse_id": str(wh_id),
                "count_date": str(date.today()),
                "count_reference": "Q3-COMMIT-01",
                "adjustment_reason": "Physical count audit adjustment",
                "counts": [{"item_id": str(item_id), "counted_quantity": "95.0000"}],
            },
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Physical count reconciliation adjustments posted successfully."
    assert "ADJ-" in data["transaction_number"]
    assert len(fake_service.commit_calls) == 1


@pytest.mark.asyncio
async def test_api_reconciliation_rbac_forbidden_for_store_keeper_and_viewer(token_factory):
    fake_service = FakeReconciliationService()
    app.dependency_overrides[get_reconciliation_service] = lambda: fake_service

    wh_id = uuid4()
    item_id = uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. STORE_KEEPER cannot preview or commit
        sk_token = token_factory(role="STORE_KEEPER")

        preview_res = await client.post(
            "/api/v1/reconciliation/preview",
            headers={"Authorization": f"Bearer {sk_token}"},
            json={
                "warehouse_id": str(wh_id),
                "count_reference": "REF",
                "counts": [{"item_id": str(item_id), "counted_quantity": "10"}],
            },
        )
        assert preview_res.status_code == 403

        commit_res = await client.post(
            "/api/v1/reconciliation/commit",
            headers={"Authorization": f"Bearer {sk_token}"},
            json={
                "warehouse_id": str(wh_id),
                "count_reference": "REF",
                "adjustment_reason": "Reason",
                "counts": [{"item_id": str(item_id), "counted_quantity": "10"}],
            },
        )
        assert commit_res.status_code == 403

        # 2. VIEWER cannot view count-sheet, preview, or commit
        v_token = token_factory(role="VIEWER")

        sheet_res = await client.get(
            f"/api/v1/reconciliation/count-sheet/{wh_id}",
            headers={"Authorization": f"Bearer {v_token}"},
        )
        assert sheet_res.status_code == 403

        commit_res2 = await client.post(
            "/api/v1/reconciliation/commit",
            headers={"Authorization": f"Bearer {v_token}"},
            json={
                "warehouse_id": str(wh_id),
                "count_reference": "REF",
                "adjustment_reason": "Reason",
                "counts": [{"item_id": str(item_id), "counted_quantity": "10"}],
            },
        )
        assert commit_res2.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_reconciliation_unauthenticated_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sheet_res = await client.get(f"/api/v1/reconciliation/count-sheet/{uuid4()}")
        assert sheet_res.status_code in (401, 403)

        preview_res = await client.post("/api/v1/reconciliation/preview", json={})
        assert preview_res.status_code in (401, 403)

        commit_res = await client.post("/api/v1/reconciliation/commit", json={})
        assert commit_res.status_code in (401, 403)
