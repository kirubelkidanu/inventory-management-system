# backend/tests/test_adjustments_and_srv.py
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt
from pydantic import ValidationError

from app.api.routes.transactions import get_transaction_service
from app.core.config import settings
from app.main import app
from app.models.inventory import InventoryBalance
from app.models.item import Item
from app.models.transaction import StockMovement, Transaction, TransactionLine
from app.schemas.transaction import (
    AdjustmentCreate,
    AdjustmentLineCreate,
    SRVCreate,
    SRVLineCreate,
    SIVReturnableItemsResponse,
    SIVReturnableLine,
    TransactionRead,
)
from app.services.transaction import TransactionService, _to_uuid


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


class FakeTransactionService:
    def __init__(self):
        self.srv_calls = []
        self.adjustment_calls = []

    async def get_siv_returnable_items(self, siv_id: UUID):
        return SIVReturnableItemsResponse(
            transaction_id=siv_id,
            transaction_number="SIV-20261105-001",
            warehouse_id=uuid4(),
            project_id=uuid4(),
            siv_no="SIV-001",
            transaction_date=date.today(),
            lines=[
                SIVReturnableLine(
                    item_id=uuid4(),
                    item_code="01-CM-00001",
                    description="Cement Grade 42.5N",
                    unit="BAG",
                    unit_price=Decimal("950.0000"),
                    issued_quantity=Decimal("50.0000"),
                    already_returned_quantity=Decimal("10.0000"),
                    remaining_returnable_quantity=Decimal("40.0000"),
                )
            ],
        )

    async def create_and_post_srv(self, user_id, payload: SRVCreate):
        self.srv_calls.append((user_id, payload))
        tx_id = uuid4()
        lines = [
            TransactionLine(
                id=uuid4(),
                transaction_id=tx_id,
                line_number=idx,
                item_id=line.item_id,
                quantity=line.quantity,
                unit=line.unit,
                remarks=line.remarks,
            )
            for idx, line in enumerate(payload.lines, start=1)
        ]
        tx = Transaction(
            id=tx_id,
            transaction_number=f"SRV-20260918-{uuid4().hex[:8].upper()}",
            transaction_type="SRV",
            status="POSTED",
            transaction_date=payload.transaction_date,
            warehouse_id=payload.warehouse_id,
            project_id=payload.project_id,
            reference_transaction_id=payload.reference_siv_id,
            remarks=payload.remarks,
            created_by=_to_uuid(user_id),
            created_at=datetime.now(timezone.utc),
            posted_by=_to_uuid(user_id),
            posted_at=datetime.now(timezone.utc),
        )
        tx.lines = lines
        return tx

    async def create_and_post_adjustment(self, user_id, payload: AdjustmentCreate):
        self.adjustment_calls.append((user_id, payload))
        tx_id = uuid4()
        lines = [
            TransactionLine(
                id=uuid4(),
                transaction_id=tx_id,
                line_number=idx,
                item_id=line.item_id,
                quantity=line.quantity,
                unit=line.unit,
                remarks=line.remarks,
            )
            for idx, line in enumerate(payload.lines, start=1)
        ]
        tx = Transaction(
            id=tx_id,
            transaction_number=f"ADJ-20260918-{uuid4().hex[:8].upper()}",
            transaction_type="ADJUSTMENT",
            status="POSTED",
            transaction_date=payload.transaction_date,
            warehouse_id=payload.warehouse_id,
            project_id=payload.project_id,
            adjustment_reason=payload.adjustment_reason,
            remarks=payload.remarks,
            created_by=_to_uuid(user_id),
            created_at=datetime.now(timezone.utc),
            posted_by=_to_uuid(user_id),
            posted_at=datetime.now(timezone.utc),
        )
        tx.lines = lines
        return tx


# ===========================================================================
# 1. Pydantic Schema Validation Tests
# ===========================================================================


def test_srv_schema_rejects_duplicate_items():
    wh_id = uuid4()
    siv_id = uuid4()
    item_id = uuid4()
    with pytest.raises(ValidationError) as exc:
        SRVCreate(
            reference_siv_id=siv_id,
            warehouse_id=wh_id,
            lines=[
                SRVLineCreate(item_id=item_id, quantity=Decimal("5"), unit="PCS"),
                SRVLineCreate(item_id=item_id, quantity=Decimal("2"), unit="PCS"),
            ],
        )
    assert "Duplicate item in transaction lines is not allowed" in str(exc.value)


def test_srv_schema_rejects_non_positive_quantity():
    item_id = uuid4()
    with pytest.raises(ValidationError):
        SRVLineCreate(item_id=item_id, quantity=Decimal("0"), unit="PCS")

    with pytest.raises(ValidationError):
        SRVLineCreate(item_id=item_id, quantity=Decimal("-1"), unit="PCS")


def test_srv_schema_rejects_empty_lines():
    with pytest.raises(ValidationError):
        SRVCreate(reference_siv_id=uuid4(), warehouse_id=uuid4(), lines=[])


def test_adjustment_schema_rejects_duplicate_items():
    wh_id = uuid4()
    item_id = uuid4()
    with pytest.raises(ValidationError) as exc:
        AdjustmentCreate(
            warehouse_id=wh_id,
            adjustment_reason="Physical count discrepancy",
            lines=[
                AdjustmentLineCreate(item_id=item_id, direction="IN", quantity=Decimal("5"), unit="PCS"),
                AdjustmentLineCreate(item_id=item_id, direction="OUT", quantity=Decimal("2"), unit="PCS"),
            ],
        )
    assert "Duplicate item in transaction lines is not allowed" in str(exc.value)


def test_adjustment_schema_rejects_empty_or_whitespace_reason():
    wh_id = uuid4()
    item_id = uuid4()
    with pytest.raises(ValidationError):
        AdjustmentCreate(
            warehouse_id=wh_id,
            adjustment_reason="",
            lines=[AdjustmentLineCreate(item_id=item_id, direction="IN", quantity=Decimal("5"), unit="PCS")],
        )

    with pytest.raises(ValidationError):
        AdjustmentCreate(
            warehouse_id=wh_id,
            adjustment_reason="    ",
            lines=[AdjustmentLineCreate(item_id=item_id, direction="IN", quantity=Decimal("5"), unit="PCS")],
        )


def test_adjustment_schema_rejects_invalid_direction():
    item_id = uuid4()
    with pytest.raises(ValidationError):
        AdjustmentLineCreate(item_id=item_id, direction="UP", quantity=Decimal("5"), unit="PCS")


def test_adjustment_schema_rejects_non_positive_quantity():
    item_id = uuid4()
    with pytest.raises(ValidationError):
        AdjustmentLineCreate(item_id=item_id, direction="IN", quantity=Decimal("0"), unit="PCS")

    with pytest.raises(ValidationError):
        AdjustmentLineCreate(item_id=item_id, direction="OUT", quantity=Decimal("-3"), unit="PCS")


# ===========================================================================
# 2. TransactionService: SRV (Store Return Voucher) Unit Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_service_srv_success():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    siv_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    # Mock referenced SIV
    ref_siv = Transaction(
        id=siv_id,
        transaction_number="SIV-20260918-ABCD1234",
        transaction_type="SIV",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=wh_id,
        project_id=uuid4(),
        created_by=user_id,
    )
    siv_line = TransactionLine(
        id=uuid4(),
        transaction_id=siv_id,
        line_number=1,
        item_id=item_id,
        quantity=Decimal("10.0000"),
        unit="BAG",
    )
    ref_siv.lines = [siv_line]

    service.repo.get_transaction_by_id = AsyncMock(side_effect=[ref_siv, None])
    service.repo.lock_inventory_balances_for_update = AsyncMock(return_value={})
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()

    initial_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("20.0000"),
        quantity_reserved=Decimal("0.0000"),
        updated_at=datetime.now(timezone.utc),
    )
    service.repo.get_or_create_balance = AsyncMock(return_value=initial_bal)
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    payload = SRVCreate(
        reference_siv_id=siv_id,
        warehouse_id=wh_id,
        lines=[SRVLineCreate(item_id=item_id, quantity=Decimal("4.0000"), unit="BAG")],
    )

    result = await service.create_and_post_srv(user_id=user_id, payload=payload)

    assert result.transaction_type == "SRV"
    assert result.status == "POSTED"
    assert result.reference_transaction_id == siv_id
    assert initial_bal.quantity_on_hand == Decimal("24.0000")

    # Movement check: movement_type IN, signed_quantity +4
    service.repo.create_stock_movement.assert_called_once()
    mov_kwargs = service.repo.create_stock_movement.call_args.kwargs
    assert mov_kwargs["movement_type"] == "IN"
    assert mov_kwargs["quantity"] == Decimal("4.0000")
    assert mov_kwargs["running_balance"] == Decimal("24.0000")

    # Audit check: POST_SRV
    service.repo.create_audit_log.assert_called_once()
    audit_kwargs = service.repo.create_audit_log.call_args.kwargs
    assert audit_kwargs["action"] in ("POST", "POST_SRV")
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_service_srv_fails_when_reference_siv_not_found():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    service.repo.get_transaction_by_id = AsyncMock(return_value=None)
    wh_id = uuid4()
    siv_id = uuid4()
    item_id = uuid4()

    payload = SRVCreate(
        reference_siv_id=siv_id,
        warehouse_id=wh_id,
        lines=[SRVLineCreate(item_id=item_id, quantity=Decimal("2.0000"), unit="PCS")],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_and_post_srv(user_id=uuid4(), payload=payload)
    assert exc.value.status_code == 404
    assert "not found" in exc.value.detail.lower()
    mock_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_service_srv_fails_when_reference_not_posted_siv():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    siv_id = uuid4()
    item_id = uuid4()

    # Case 1: Transaction is GRV instead of SIV
    grv_tx = Transaction(
        id=siv_id,
        transaction_number="GRV-20260918-0001",
        transaction_type="GRV",
        status="POSTED",
        created_by=uuid4(),
    )
    service.repo.get_transaction_by_id = AsyncMock(return_value=grv_tx)

    payload = SRVCreate(
        reference_siv_id=siv_id,
        warehouse_id=wh_id,
        lines=[SRVLineCreate(item_id=item_id, quantity=Decimal("2.0000"), unit="PCS")],
    )

    with pytest.raises(HTTPException) as exc1:
        await service.create_and_post_srv(user_id=uuid4(), payload=payload)
    assert exc1.value.status_code == 400
    assert "not an siv" in exc1.value.detail.lower()

    # Case 2: Transaction is SIV but status is DRAFT
    draft_siv = Transaction(
        id=siv_id,
        transaction_number="SIV-20260918-0002",
        transaction_type="SIV",
        status="DRAFT",
        created_by=uuid4(),
    )
    service.repo.get_transaction_by_id = AsyncMock(return_value=draft_siv)

    with pytest.raises(HTTPException) as exc2:
        await service.create_and_post_srv(user_id=uuid4(), payload=payload)
    assert exc2.value.status_code == 400
    assert "not posted" in exc2.value.detail.lower()


@pytest.mark.asyncio
async def test_service_srv_fails_when_item_not_in_siv():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    siv_id = uuid4()
    item_siv = uuid4()
    item_other = uuid4()

    ref_siv = Transaction(
        id=siv_id,
        transaction_number="SIV-20260918-0003",
        transaction_type="SIV",
        status="POSTED",
        created_by=uuid4(),
    )
    ref_siv.lines = [
        TransactionLine(
            id=uuid4(),
            transaction_id=siv_id,
            line_number=1,
            item_id=item_siv,
            quantity=Decimal("10.0000"),
            unit="BAG",
        )
    ]
    service.repo.get_transaction_by_id = AsyncMock(return_value=ref_siv)

    payload = SRVCreate(
        reference_siv_id=siv_id,
        warehouse_id=wh_id,
        lines=[SRVLineCreate(item_id=item_other, quantity=Decimal("1.0000"), unit="BAG")],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_and_post_srv(user_id=uuid4(), payload=payload)
    assert exc.value.status_code == 400
    assert "was not issued on referenced siv" in exc.value.detail.lower()
@pytest.mark.asyncio
async def test_service_srv_inherits_unit_price_from_originating_siv():
    """Confirms SRV line inherits unit_price from the originating SIV line."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    siv_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    siv_line = TransactionLine(
        id=uuid4(),
        transaction_id=siv_id,
        line_number=1,
        item_id=item_id,
        quantity=Decimal("50.0000"),
        unit="BAG",
        unit_price=Decimal("850.5000"),
    )
    ref_siv = Transaction(
        id=siv_id,
        transaction_number="SIV-20261105-001",
        transaction_type="SIV",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=wh_id,
        lines=[siv_line],
    )
    service.repo.get_transaction_by_id = AsyncMock(side_effect=[ref_siv, None])
    service.repo.get_returned_quantities_for_siv = AsyncMock(return_value={})
    service.repo.lock_inventory_balances_for_update = AsyncMock(return_value={})
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()
    service.repo.get_or_create_balance = AsyncMock(return_value=InventoryBalance(
        id=uuid4(), warehouse_id=wh_id, item_id=item_id, quantity_on_hand=Decimal("10.0000"), quantity_reserved=Decimal("0.0000")
    ))
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    payload = SRVCreate(
        reference_siv_id=siv_id,
        warehouse_id=wh_id,
        lines=[SRVLineCreate(item_id=item_id, quantity=Decimal("5.0000"), unit="BAG")],
    )

    await service.create_and_post_srv(user_id=user_id, payload=payload)

    service.repo.create_transaction_lines.assert_awaited_once()
    saved_lines = service.repo.create_transaction_lines.await_args[0][0]
    assert len(saved_lines) == 1
    assert saved_lines[0].unit_price == Decimal("850.5000")
    assert saved_lines[0].quantity == Decimal("5.0000")


@pytest.mark.asyncio
async def test_service_srv_partial_return_and_stock_movements():
    """Confirms partial SRV return increments stock on hand (+IN) and creates IN movement."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    siv_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    siv_line = TransactionLine(
        id=uuid4(),
        transaction_id=siv_id,
        line_number=1,
        item_id=item_id,
        quantity=Decimal("30.0000"),
        unit="PCS",
        unit_price=Decimal("120.0000"),
    )
    ref_siv = Transaction(
        id=siv_id,
        transaction_number="SIV-20261105-002",
        transaction_type="SIV",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=wh_id,
        lines=[siv_line],
    )
    service.repo.get_transaction_by_id = AsyncMock(side_effect=[ref_siv, None])
    service.repo.get_returned_quantities_for_siv = AsyncMock(return_value={})
    service.repo.lock_inventory_balances_for_update = AsyncMock(return_value={})
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()
    balance = InventoryBalance(
        id=uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("5.0000"),
        quantity_reserved=Decimal("0.0000"),
    )
    service.repo.get_or_create_balance = AsyncMock(return_value=balance)
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    payload = SRVCreate(
        reference_siv_id=siv_id,
        warehouse_id=wh_id,
        lines=[SRVLineCreate(item_id=item_id, quantity=Decimal("12.0000"), unit="PCS")],
    )

    result = await service.create_and_post_srv(user_id=user_id, payload=payload)
    assert result.transaction_type == "SRV"
    assert balance.quantity_on_hand == Decimal("17.0000")

    service.repo.create_stock_movement.assert_called_once()
    mov = service.repo.create_stock_movement.call_args.kwargs
    assert mov["movement_type"] == "IN"
    assert mov["quantity"] == Decimal("12.0000")
    assert mov["running_balance"] == Decimal("17.0000")


@pytest.mark.asyncio
async def test_service_srv_rejects_over_return():
    """Confirms attempting to return more than originally issued raises HTTP 400 Bad Request."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    siv_id = uuid4()
    item_id = uuid4()

    mock_item = Item(id=item_id, item_code="01-CM-00001", description="Cement")
    siv_line = TransactionLine(
        id=uuid4(),
        transaction_id=siv_id,
        line_number=1,
        item_id=item_id,
        quantity=Decimal("20.0000"),
        unit="BAG",
        item=mock_item,
    )
    ref_siv = Transaction(
        id=siv_id,
        transaction_number="SIV-20261105-003",
        transaction_type="SIV",
        status="POSTED",
        warehouse_id=wh_id,
        lines=[siv_line],
    )
    service.repo.get_transaction_by_id = AsyncMock(return_value=ref_siv)
    service.repo.get_returned_quantities_for_siv = AsyncMock(return_value={})

    payload = SRVCreate(
        reference_siv_id=siv_id,
        warehouse_id=wh_id,
        lines=[SRVLineCreate(item_id=item_id, quantity=Decimal("25.0000"), unit="BAG")],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_and_post_srv(user_id=uuid4(), payload=payload)
    assert exc.value.status_code == 400
    assert "exceeds remaining returnable quantity (20.0000)" in exc.value.detail
    assert "01-CM-00001" in exc.value.detail


@pytest.mark.asyncio
async def test_service_srv_multiple_partial_returns_cumulative_cap():
    """Confirms cumulative previously returned quantities enforce strict over-return prevention."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    siv_id = uuid4()
    item_id = uuid4()

    mock_item = Item(id=item_id, item_code="02-ST-00001", description="Rebar 12mm")
    siv_line = TransactionLine(
        id=uuid4(),
        transaction_id=siv_id,
        line_number=1,
        item_id=item_id,
        quantity=Decimal("100.0000"),
        unit="PCS",
        item=mock_item,
    )
    ref_siv = Transaction(
        id=siv_id,
        transaction_number="SIV-20261105-004",
        transaction_type="SIV",
        status="POSTED",
        warehouse_id=wh_id,
        lines=[siv_line],
    )
    service.repo.get_transaction_by_id = AsyncMock(return_value=ref_siv)
    service.repo.get_returned_quantities_for_siv = AsyncMock(
        return_value={item_id: Decimal("60.0000")}
    )

    # Attempt to return 45 (remaining is 40)
    payload = SRVCreate(
        reference_siv_id=siv_id,
        warehouse_id=wh_id,
        lines=[SRVLineCreate(item_id=item_id, quantity=Decimal("45.0000"), unit="PCS")],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_and_post_srv(user_id=uuid4(), payload=payload)
    assert exc.value.status_code == 400
    assert "exceeds remaining returnable quantity (40.0000)" in exc.value.detail


@pytest.mark.asyncio
async def test_service_get_siv_returnable_items():
    """Confirms get_siv_returnable_items returns correct metadata and remaining returnable lines."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    siv_id = uuid4()
    wh_id = uuid4()
    item_id = uuid4()

    mock_item = Item(id=item_id, item_code="01-CM-00001", description="Cement Grade 42.5N")
    siv_line = TransactionLine(
        id=uuid4(),
        transaction_id=siv_id,
        line_number=1,
        item_id=item_id,
        quantity=Decimal("50.0000"),
        unit="BAG",
        unit_price=Decimal("950.0000"),
        item=mock_item,
    )
    siv = Transaction(
        id=siv_id,
        transaction_number="SIV-20261105-005",
        transaction_type="SIV",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=wh_id,
        lines=[siv_line],
    )
    service.repo.get_transaction_with_lines_and_items = AsyncMock(return_value=siv)
    service.repo.get_returned_quantities_for_siv = AsyncMock(
        return_value={item_id: Decimal("20.0000")}
    )

    resp = await service.get_siv_returnable_items(siv_id)
    assert resp.transaction_id == siv_id
    assert resp.transaction_number == "SIV-20261105-005"
    assert resp.warehouse_id == wh_id
    assert len(resp.lines) == 1
    line = resp.lines[0]
    assert line.item_id == item_id
    assert line.item_code == "01-CM-00001"
    assert line.issued_quantity == Decimal("50.0000")
    assert line.already_returned_quantity == Decimal("20.0000")
    assert line.remaining_returnable_quantity == Decimal("30.0000")
    assert line.unit_price == Decimal("950.0000")


@pytest.mark.asyncio
async def test_api_get_siv_returnable_items(token_factory):
    """Confirms GET /api/v1/transactions/siv/{siv_id}/returnable-items responds correctly."""
    fake_service = FakeTransactionService()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role="STORE_KEEPER")
    siv_id = uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(
            f"/api/v1/transactions/siv/{siv_id}/returnable-items",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == str(siv_id)
    assert len(data["lines"]) == 1
    assert data["lines"][0]["remaining_returnable_quantity"] == "40.0000"



# ===========================================================================
# 3. TransactionService: ADJUSTMENT Unit Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_service_adjustment_in_success():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    initial_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("50.0000"),
        quantity_reserved=Decimal("0.0000"),
        updated_at=datetime.now(timezone.utc),
    )
    service.repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item_id: initial_bal}
    )
    service.repo.get_or_create_balance = AsyncMock(return_value=initial_bal)
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()
    service.repo.get_transaction_by_id = AsyncMock(return_value=None)

    payload = AdjustmentCreate(
        warehouse_id=wh_id,
        adjustment_reason="Found surplus during quarterly physical count",
        lines=[
            AdjustmentLineCreate(
                item_id=item_id, direction="IN", quantity=Decimal("10.0000"), unit="PCS"
            )
        ],
    )

    result = await service.create_and_post_adjustment(user_id=user_id, payload=payload)

    assert result.transaction_type == "ADJUSTMENT"
    assert result.status == "POSTED"
    assert result.adjustment_reason == "Found surplus during quarterly physical count"
    assert initial_bal.quantity_on_hand == Decimal("60.0000")

    # Stock movement check
    service.repo.create_stock_movement.assert_called_once()
    mov_kwargs = service.repo.create_stock_movement.call_args.kwargs
    assert mov_kwargs["movement_type"] == "IN"
    assert mov_kwargs["quantity"] == Decimal("10.0000")
    assert mov_kwargs["running_balance"] == Decimal("60.0000")

    # Audit log check
    service.repo.create_audit_log.assert_called_once()
    audit_kwargs = service.repo.create_audit_log.call_args.kwargs
    assert audit_kwargs["action"] == "POST_ADJUSTMENT"
    assert audit_kwargs["reason"] == "Found surplus during quarterly physical count"
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_service_adjustment_out_success():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    initial_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("50.0000"),
        quantity_reserved=Decimal("5.0000"),  # available = 45.0000
        updated_at=datetime.now(timezone.utc),
    )
    service.repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item_id: initial_bal}
    )
    service.repo.get_or_create_balance = AsyncMock(return_value=initial_bal)
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()
    service.repo.get_transaction_by_id = AsyncMock(return_value=None)

    payload = AdjustmentCreate(
        warehouse_id=wh_id,
        adjustment_reason="Damaged items written off",
        lines=[
            AdjustmentLineCreate(
                item_id=item_id, direction="OUT", quantity=Decimal("15.0000"), unit="PCS"
            )
        ],
    )

    result = await service.create_and_post_adjustment(user_id=user_id, payload=payload)

    assert result.transaction_type == "ADJUSTMENT"
    assert result.status == "POSTED"
    assert initial_bal.quantity_on_hand == Decimal("35.0000")

    # Stock movement check
    service.repo.create_stock_movement.assert_called_once()
    mov_kwargs = service.repo.create_stock_movement.call_args.kwargs
    assert mov_kwargs["movement_type"] == "OUT"
    assert mov_kwargs["quantity"] == Decimal("15.0000")
    assert mov_kwargs["running_balance"] == Decimal("35.0000")

    # Audit log check
    service.repo.create_audit_log.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_service_adjustment_out_fails_when_stock_insufficient():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    initial_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("10.0000"),
        quantity_reserved=Decimal("2.0000"),  # available = 8.0000
        updated_at=datetime.now(timezone.utc),
    )
    service.repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item_id: initial_bal}
    )

    # Attempt to write off 9.0000 (more than available 8.0000)
    payload = AdjustmentCreate(
        warehouse_id=wh_id,
        adjustment_reason="Damaged stock scrap",
        lines=[
            AdjustmentLineCreate(
                item_id=item_id, direction="OUT", quantity=Decimal("9.0000"), unit="PCS"
            )
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_and_post_adjustment(user_id=user_id, payload=payload)

    assert exc.value.status_code == 400
    assert "insufficient stock" in exc.value.detail.lower()
    assert initial_bal.quantity_on_hand == Decimal("10.0000")  # untouched
    mock_session.rollback.assert_called_once()


# ===========================================================================
# 4. API Endpoints & RBAC Authorization Tests
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER"])
async def test_api_srv_authorized_roles_succeed(token_factory, role):
    fake_service = FakeTransactionService()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role=role)

    wh_id = str(uuid4())
    siv_id = str(uuid4())
    item_id = str(uuid4())

    payload = {
        "reference_siv_id": siv_id,
        "warehouse_id": wh_id,
        "lines": [{"item_id": item_id, "quantity": 3.0, "unit": "BAG"}],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/transactions/srv",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 201
    data = response.json()
    assert data["transaction_type"] == "SRV"
    assert data["status"] == "POSTED"
    assert data["reference_transaction_id"] == siv_id
    assert len(data["lines"]) == 1


@pytest.mark.asyncio
async def test_api_srv_viewer_is_forbidden(token_factory):
    fake_service = FakeTransactionService()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role="VIEWER")

    payload = {
        "reference_siv_id": str(uuid4()),
        "warehouse_id": str(uuid4()),
        "lines": [{"item_id": str(uuid4()), "quantity": 1.0, "unit": "BAG"}],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/transactions/srv",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["ADMIN", "INVENTORY_MANAGER"])
async def test_api_adjustment_authorized_roles_succeed(token_factory, role):
    fake_service = FakeTransactionService()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role=role)

    wh_id = str(uuid4())
    item_id = str(uuid4())

    payload = {
        "warehouse_id": wh_id,
        "adjustment_reason": "Stock count correction authorized by management",
        "lines": [{"item_id": item_id, "direction": "IN", "quantity": 10.0, "unit": "PCS"}],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/transactions/adjustment",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 201
    data = response.json()
    assert data["transaction_type"] == "ADJUSTMENT"
    assert data["status"] == "POSTED"
    assert data["adjustment_reason"] == "Stock count correction authorized by management"
    assert len(data["lines"]) == 1


@pytest.mark.asyncio
async def test_api_adjustment_store_keeper_is_forbidden(token_factory):
    fake_service = FakeTransactionService()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role="STORE_KEEPER")

    payload = {
        "warehouse_id": str(uuid4()),
        "adjustment_reason": "Store keeper attempting unapproved adjustment",
        "lines": [{"item_id": str(uuid4()), "direction": "OUT", "quantity": 1.0, "unit": "PCS"}],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/transactions/adjustment",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_adjustment_viewer_is_forbidden(token_factory):
    fake_service = FakeTransactionService()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role="VIEWER")

    payload = {
        "warehouse_id": str(uuid4()),
        "adjustment_reason": "Viewer attempting adjustment",
        "lines": [{"item_id": str(uuid4()), "direction": "IN", "quantity": 5.0, "unit": "PCS"}],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/transactions/adjustment",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_adjustment_fails_validation_without_reason(token_factory):
    token = token_factory(role="ADMIN")

    # Missing reason
    payload_no_reason = {
        "warehouse_id": str(uuid4()),
        "lines": [{"item_id": str(uuid4()), "direction": "IN", "quantity": 5.0, "unit": "PCS"}],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res1 = await client.post(
            "/api/v1/transactions/adjustment",
            json=payload_no_reason,
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res1.status_code == 422

    # Whitespace reason
    payload_whitespace_reason = {
        "warehouse_id": str(uuid4()),
        "adjustment_reason": "   ",
        "lines": [{"item_id": str(uuid4()), "direction": "IN", "quantity": 5.0, "unit": "PCS"}],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res2 = await client.post(
            "/api/v1/transactions/adjustment",
            json=payload_whitespace_reason,
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res2.status_code == 422
