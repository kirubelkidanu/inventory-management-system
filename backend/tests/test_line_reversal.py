import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.api.routes.transactions import get_transaction_service
from app.core.config import settings
from app.main import app
from app.models.inventory import InventoryBalance
from app.models.transaction import (
    StockMovement,
    Transaction,
    TransactionLine,
    TransferLine,
    TransferRecord,
)
from app.models.user import User
from app.services.transaction import TransactionService


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


# ---------------------------------------------------------------------------
# 1. Unit & Service Layer Tests: TransactionService.void_transaction_line
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_void_istv_line_restores_source_balance_and_removes_from_transit():
    """
    Voiding 1 line of a multi-line ISTV:
    - Restores source warehouse balance.
    - Removes only that line from in-transit tracking while keeping remaining lines in transit.
    - Records compensating IN movement + audit log.
    - Parent transaction remains POSTED because line 2 is still active.
    """
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    source_wh_id = uuid.uuid4()
    dest_wh_id = uuid.uuid4()
    item1_id = uuid.uuid4()
    item2_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    line1_id = uuid.uuid4()
    line2_id = uuid.uuid4()
    tr_id = uuid.uuid4()
    tl1_id = uuid.uuid4()
    tl2_id = uuid.uuid4()

    line1 = TransactionLine(
        id=line1_id,
        transaction_id=tx_id,
        line_number=1,
        item_id=item1_id,
        quantity=Decimal("50.0000"),
        unit="PCS",
        is_voided=False,
    )
    line2 = TransactionLine(
        id=line2_id,
        transaction_id=tx_id,
        line_number=2,
        item_id=item2_id,
        quantity=Decimal("30.0000"),
        unit="PCS",
        is_voided=False,
    )
    tx = Transaction(
        id=tx_id,
        transaction_number="ISTV-20261019-11111111",
        transaction_type="ISTV",
        status="POSTED",
        transaction_date=date.today(),
        source_warehouse_id=source_wh_id,
        destination_warehouse_id=dest_wh_id,
        warehouse_id=source_wh_id,
        created_by=uuid.uuid4(),
    )
    tx.lines = [line1, line2]

    tl1 = TransferLine(
        id=tl1_id,
        transfer_record_id=tr_id,
        item_id=item1_id,
        sent_quantity=Decimal("50.0000"),
        received_quantity=Decimal("0.0000"),
    )
    tl2 = TransferLine(
        id=tl2_id,
        transfer_record_id=tr_id,
        item_id=item2_id,
        sent_quantity=Decimal("30.0000"),
        received_quantity=Decimal("0.0000"),
    )
    transfer_record = TransferRecord(
        id=tr_id,
        istv_transaction_id=tx_id,
        source_warehouse_id=source_wh_id,
        destination_warehouse_id=dest_wh_id,
        status="IN_TRANSIT",
    )
    transfer_record.lines = [tl1, tl2]

    source_bal = InventoryBalance(
        id=uuid.uuid4(),
        warehouse_id=source_wh_id,
        item_id=item1_id,
        quantity_on_hand=Decimal("100.0000"),
        quantity_reserved=Decimal("0.0000"),
    )

    # Mock DB executions
    # 1. select Transaction
    res_tx = MagicMock()
    res_tx.scalar_one_or_none.return_value = tx

    # 2. select TransactionLine
    res_lines = MagicMock()
    res_lines.scalars.return_value.all.return_value = [line1, line2]

    # 3. select TransferRecord
    res_tr = MagicMock()
    res_tr.scalar_one_or_none.return_value = transfer_record

    # 4. select remaining TransferLines
    res_rem = MagicMock()
    res_rem.scalars.return_value.all.return_value = [tl2]

    mock_session.execute = AsyncMock(side_effect=[res_tx, res_lines, res_tr, res_rem])
    service.repo.get_or_create_balance = AsyncMock(return_value=source_bal)
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()
    service.repo.get_transaction_by_id = AsyncMock(return_value=tx)

    admin_user = User(
        id=uuid.uuid4(),
        auth_user_id=uuid.uuid4(),
        email="admin@test.local",
        full_name="Admin",
        role="ADMIN",
        is_active=True,
    )

    res = await service.void_transaction_line(
        transaction_id=tx_id,
        line_id=line1_id,
        reason="Entered wrong source item",
        actor_user=admin_user,
    )

    # 1. Balance restored
    assert source_bal.quantity_on_hand == Decimal("150.0000")

    # 2. Line 1 voided, Line 2 active
    assert line1.is_voided is True
    assert line1.void_reason == "Entered wrong source item"
    assert line1.voided_by == admin_user.id
    assert line2.is_voided is False

    # 3. Parent tx still POSTED because line 2 is still active
    assert tx.status == "POSTED"

    # 4. Compensating stock movement IN
    service.repo.create_stock_movement.assert_awaited_once()
    sm_args = service.repo.create_stock_movement.await_args[1]
    assert sm_args["movement_type"] == "IN"
    assert sm_args["quantity"] == Decimal("50.0000")
    assert sm_args["running_balance"] == Decimal("150.0000")

    # 5. TransferLine 1 deleted
    mock_session.delete.assert_called_once_with(tl1)

    # 6. TransferRecord status remains IN_TRANSIT (line 2 still in transit)
    assert transfer_record.status == "IN_TRANSIT"

    # 7. Audit log recorded with action = 'CANCEL'
    service.repo.create_audit_log.assert_awaited_once()
    audit_args = service.repo.create_audit_log.await_args[1]
    assert audit_args["action"] == "CANCEL"
    assert audit_args["entity_type"] == "transaction_line"
    assert audit_args["entity_id"] == str(line1_id)

    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_void_istv_line_rejected_if_already_received():
    """
    Attempting to void an ISTV line that already has an ISTRV receipt is rejected (HTTP 400).
    """
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    source_wh_id = uuid.uuid4()
    dest_wh_id = uuid.uuid4()
    item_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    line_id = uuid.uuid4()
    tr_id = uuid.uuid4()

    line = TransactionLine(
        id=line_id,
        transaction_id=tx_id,
        line_number=1,
        item_id=item_id,
        quantity=Decimal("50.0000"),
        unit="PCS",
        is_voided=False,
    )
    tx = Transaction(
        id=tx_id,
        transaction_number="ISTV-20261019-22222222",
        transaction_type="ISTV",
        status="POSTED",
        transaction_date=date.today(),
        source_warehouse_id=source_wh_id,
        destination_warehouse_id=dest_wh_id,
        warehouse_id=source_wh_id,
        created_by=uuid.uuid4(),
    )
    tx.lines = [line]

    tl = TransferLine(
        id=uuid.uuid4(),
        transfer_record_id=tr_id,
        item_id=item_id,
        sent_quantity=Decimal("50.0000"),
        received_quantity=Decimal("20.0000"),  # Partially received!
    )
    transfer_record = TransferRecord(
        id=tr_id,
        istv_transaction_id=tx_id,
        source_warehouse_id=source_wh_id,
        destination_warehouse_id=dest_wh_id,
        status="PARTIALLY_RECEIVED",
    )
    transfer_record.lines = [tl]

    res_tx = MagicMock()
    res_tx.scalar_one_or_none.return_value = tx

    res_lines = MagicMock()
    res_lines.scalars.return_value.all.return_value = [line]

    res_tr = MagicMock()
    res_tr.scalar_one_or_none.return_value = transfer_record

    mock_session.execute = AsyncMock(side_effect=[res_tx, res_lines, res_tr])

    admin_user = User(
        id=uuid.uuid4(),
        auth_user_id=uuid.uuid4(),
        email="manager@test.local",
        full_name="Manager",
        role="INVENTORY_MANAGER",
        is_active=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.void_transaction_line(
            transaction_id=tx_id,
            line_id=line_id,
            reason="Mistaken line entry",
            actor_user=admin_user,
        )

    assert exc_info.value.status_code == 400
    assert "already been partially or fully received" in exc_info.value.detail


@pytest.mark.asyncio
async def test_void_istrv_line_reverses_destination_balance_and_restores_transit_remaining():
    """
    Voiding 1 line of an ISTRV:
    - Decrements destination warehouse balance via compensating OUT movement.
    - Restores in-transit remaining quantity by decrementing received_quantity on transfer_lines.
    - Updates transfer_record status back to IN_TRANSIT.
    """
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    dest_wh_id = uuid.uuid4()
    item_id = uuid.uuid4()
    istv_tx_id = uuid.uuid4()
    istrv_tx_id = uuid.uuid4()
    line_id = uuid.uuid4()
    tr_id = uuid.uuid4()

    line = TransactionLine(
        id=line_id,
        transaction_id=istrv_tx_id,
        line_number=1,
        item_id=item_id,
        quantity=Decimal("30.0000"),
        unit="PCS",
        is_voided=False,
    )
    istrv_tx = Transaction(
        id=istrv_tx_id,
        transaction_number="ISTRV-20261019-33333333",
        transaction_type="ISTRV",
        status="POSTED",
        transaction_date=date.today(),
        destination_warehouse_id=dest_wh_id,
        warehouse_id=dest_wh_id,
        reference_transaction_id=istv_tx_id,
        created_by=uuid.uuid4(),
    )
    istrv_tx.lines = [line]

    # Destination warehouse has 30.0000 available
    dest_bal = InventoryBalance(
        id=uuid.uuid4(),
        warehouse_id=dest_wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("30.0000"),
        quantity_reserved=Decimal("0.0000"),
    )

    # Originating transfer line has sent=50, received=30 (remaining was 20)
    tl = TransferLine(
        id=uuid.uuid4(),
        transfer_record_id=tr_id,
        item_id=item_id,
        sent_quantity=Decimal("50.0000"),
        received_quantity=Decimal("30.0000"),
    )
    transfer_record = TransferRecord(
        id=tr_id,
        istv_transaction_id=istv_tx_id,
        source_warehouse_id=uuid.uuid4(),
        destination_warehouse_id=dest_wh_id,
        status="PARTIALLY_RECEIVED",
    )
    transfer_record.lines = [tl]

    res_tx = MagicMock()
    res_tx.scalar_one_or_none.return_value = istrv_tx

    res_lines = MagicMock()
    res_lines.scalars.return_value.all.return_value = [line]

    # select TransferLine for update
    res_tl = MagicMock()
    res_tl.scalar_one_or_none.return_value = tl

    # select all TransferLines on transfer_record
    res_all_tls = MagicMock()
    res_all_tls.scalars.return_value.all.return_value = [tl]

    mock_session.execute = AsyncMock(side_effect=[res_tx, res_lines, res_tl, res_all_tls])
    service.repo.get_or_create_balance = AsyncMock(return_value=dest_bal)
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()
    service.repo.get_transfer_record_by_istv_id = AsyncMock(return_value=transfer_record)
    service.repo.get_transaction_by_id = AsyncMock(return_value=istrv_tx)

    admin_user = User(
        id=uuid.uuid4(),
        auth_user_id=uuid.uuid4(),
        email="admin@test.local",
        full_name="Admin",
        role="ADMIN",
        is_active=True,
    )

    await service.void_transaction_line(
        transaction_id=istrv_tx_id,
        line_id=line_id,
        reason="Goods damaged on arrival; returned to transit",
        actor_user=admin_user,
    )

    # 1. Destination balance decremented by 30
    assert dest_bal.quantity_on_hand == Decimal("0.0000")

    # 2. Transfer line received_quantity decremented back to 0 (remaining restored to 50)
    assert tl.received_quantity == Decimal("0.0000")
    assert tl.remaining_quantity == Decimal("50.0000")

    # 3. TransferRecord status reverted to IN_TRANSIT
    assert transfer_record.status == "IN_TRANSIT"

    # 4. Compensating OUT movement appended
    sm_args = service.repo.create_stock_movement.await_args[1]
    assert sm_args["movement_type"] == "OUT"
    assert sm_args["quantity"] == Decimal("30.0000")
    assert sm_args["running_balance"] == Decimal("0.0000")

    # 5. Parent ISTRV voucher had only 1 line, so it transitions to CANCELLED
    assert istrv_tx.status == "CANCELLED"
    assert istrv_tx.cancellation_reason == "Goods damaged on arrival; returned to transit"


@pytest.mark.asyncio
async def test_void_srv_and_siv_line_exact_balance_reversal():
    """
    Voiding an SRV line (originally IN) reverses destination stock via OUT.
    Voiding an SIV line (originally OUT) restores warehouse stock via IN.
    """
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid.uuid4()
    item_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    line_id = uuid.uuid4()

    # Test SRV Line Voiding
    srv_line = TransactionLine(
        id=line_id,
        transaction_id=tx_id,
        line_number=1,
        item_id=item_id,
        quantity=Decimal("25.0000"),
        unit="PCS",
        is_voided=False,
    )
    srv_tx = Transaction(
        id=tx_id,
        transaction_number="SRV-20261019-44444444",
        transaction_type="SRV",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=wh_id,
        created_by=uuid.uuid4(),
    )
    srv_tx.lines = [srv_line]

    bal = InventoryBalance(
        id=uuid.uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("100.0000"),
        quantity_reserved=Decimal("0.0000"),
    )

    res_tx = MagicMock()
    res_tx.scalar_one_or_none.return_value = srv_tx
    res_lines = MagicMock()
    res_lines.scalars.return_value.all.return_value = [srv_line]

    mock_session.execute = AsyncMock(side_effect=[res_tx, res_lines])
    service.repo.get_or_create_balance = AsyncMock(return_value=bal)
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()
    service.repo.get_transaction_by_id = AsyncMock(return_value=srv_tx)

    admin_user = User(
        id=uuid.uuid4(),
        auth_user_id=uuid.uuid4(),
        email="admin@test.local",
        full_name="Admin",
        role="ADMIN",
        is_active=True,
    )

    await service.void_transaction_line(
        transaction_id=tx_id,
        line_id=line_id,
        reason="SRV return rejected by warehouse keeper",
        actor_user=admin_user,
    )

    # SRV originally increased stock by 25; voiding decrements it back to 75
    assert bal.quantity_on_hand == Decimal("75.0000")
    sm_args = service.repo.create_stock_movement.await_args[1]
    assert sm_args["movement_type"] == "OUT"
    assert sm_args["quantity"] == Decimal("25.0000")


@pytest.mark.asyncio
async def test_void_line_blocks_negative_stock():
    """
    Voiding an inbound line (GRV) is rejected if warehouse stock has already been issued/consumed
    and reversing the line would cause negative stock.
    """
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid.uuid4()
    item_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    line_id = uuid.uuid4()

    line = TransactionLine(
        id=line_id,
        transaction_id=tx_id,
        line_number=1,
        item_id=item_id,
        quantity=Decimal("100.0000"),
        unit="BAG",
        is_voided=False,
    )
    tx = Transaction(
        id=tx_id,
        transaction_number="GRV-20261019-55555555",
        transaction_type="GRV",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=wh_id,
        created_by=uuid.uuid4(),
    )
    tx.lines = [line]

    # Only 30 bags remaining on hand (70 were already issued)
    bal = InventoryBalance(
        id=uuid.uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("30.0000"),
        quantity_reserved=Decimal("0.0000"),
    )

    res_tx = MagicMock()
    res_tx.scalar_one_or_none.return_value = tx
    res_lines = MagicMock()
    res_lines.scalars.return_value.all.return_value = [line]

    mock_session.execute = AsyncMock(side_effect=[res_tx, res_lines])
    service.repo.get_or_create_balance = AsyncMock(return_value=bal)

    admin_user = User(
        id=uuid.uuid4(),
        auth_user_id=uuid.uuid4(),
        email="admin@test.local",
        full_name="Admin",
        role="ADMIN",
        is_active=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.void_transaction_line(
            transaction_id=tx_id,
            line_id=line_id,
            reason="Voiding receipt",
            actor_user=admin_user,
        )

    assert exc_info.value.status_code == 400
    assert "would cause negative inventory" in exc_info.value.detail


@pytest.mark.asyncio
async def test_void_line_validation_reason_and_already_voided():
    """
    Validates that:
    1. Reason must be >= 3 characters.
    2. Attempting to void an already voided line raises HTTP 400.
    """
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    tx_id = uuid.uuid4()
    line_id = uuid.uuid4()

    admin_user = User(
        id=uuid.uuid4(),
        auth_user_id=uuid.uuid4(),
        email="admin@test.local",
        full_name="Admin",
        role="ADMIN",
        is_active=True,
    )

    # 1. Blank reason
    with pytest.raises(HTTPException) as exc_info:
        await service.void_transaction_line(
            transaction_id=tx_id,
            line_id=line_id,
            reason="   ",
            actor_user=admin_user,
        )
    assert exc_info.value.status_code == 400
    assert "cancellation reason" in exc_info.value.detail

    # 2. Already voided line
    line = TransactionLine(
        id=line_id,
        transaction_id=tx_id,
        line_number=1,
        item_id=uuid.uuid4(),
        quantity=Decimal("10.0000"),
        unit="PCS",
        is_voided=True,  # Already voided!
        void_reason="Previously voided",
    )
    tx = Transaction(
        id=tx_id,
        transaction_number="GRV-20261019-66666666",
        transaction_type="GRV",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
    )
    tx.lines = [line]

    res_tx = MagicMock()
    res_tx.scalar_one_or_none.return_value = tx
    res_lines = MagicMock()
    res_lines.scalars.return_value.all.return_value = [line]

    mock_session.execute = AsyncMock(side_effect=[res_tx, res_lines])

    with pytest.raises(HTTPException) as exc_info2:
        await service.void_transaction_line(
            transaction_id=tx_id,
            line_id=line_id,
            reason="Trying to void again",
            actor_user=admin_user,
        )
    assert exc_info2.value.status_code == 400
    assert "already voided" in exc_info2.value.detail


# ---------------------------------------------------------------------------
# 2. API Endpoint & Role Authorization Tests (HTTP Route Layer)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_void_line_endpoint_admin_and_manager_succeed(token_factory):
    """
    POST /api/v1/transactions/{tx_id}/lines/{line_id}/void succeeds for ADMIN and INVENTORY_MANAGER.
    """
    fake_service = MagicMock()
    tx_id = uuid.uuid4()
    line_id = uuid.uuid4()

    mock_tx = Transaction(
        id=tx_id,
        transaction_number="GRV-20261019-77777777",
        transaction_type="GRV",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
    )
    mock_line = TransactionLine(
        id=line_id,
        transaction_id=tx_id,
        line_number=1,
        item_id=uuid.uuid4(),
        quantity=Decimal("10.0000"),
        unit="PCS",
        is_voided=True,
        void_reason="Valid cancellation reason",
    )
    mock_tx.lines = [mock_line]
    fake_service.void_transaction_line = AsyncMock(return_value=mock_tx)

    app.dependency_overrides[get_transaction_service] = lambda: fake_service

    for role in ["ADMIN", "INVENTORY_MANAGER"]:
        token = token_factory(role=role)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/v1/transactions/{tx_id}/lines/{line_id}/void",
                json={"reason": "Valid cancellation reason"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200, f"Role {role} failed with {response.status_code}"
        data = response.json()
        assert data["id"] == str(tx_id)
        assert data["lines"][0]["is_voided"] is True

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_void_line_endpoint_storekeeper_and_viewer_are_forbidden(token_factory):
    """
    POST /api/v1/transactions/{tx_id}/lines/{line_id}/void returns 403 Forbidden
    for STORE_KEEPER and VIEWER roles.
    """
    fake_service = MagicMock()
    tx_id = uuid.uuid4()
    line_id = uuid.uuid4()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service

    for role in ["STORE_KEEPER", "VIEWER"]:
        token = token_factory(role=role)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/v1/transactions/{tx_id}/lines/{line_id}/void",
                json={"reason": "Store keeper attempting void"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()

    app.dependency_overrides.clear()
