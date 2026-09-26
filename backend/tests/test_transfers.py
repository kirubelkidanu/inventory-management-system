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
from app.models.transaction import (
    StockMovement,
    Transaction,
    TransactionLine,
    TransferLine,
    TransferRecord,
)
from app.schemas.transaction import (
    ISTRVCreate,
    ISTRVLineCreate,
    ISTVCreate,
    TransactionLineCreate,
    TransferRecordRead,
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


class FakeTransferService:
    def __init__(self):
        self.transfers: dict[UUID, TransferRecord] = {}

    async def create_and_post_istv(self, user_id, payload: ISTVCreate):
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
            transaction_number=f"ISTV-20260918-{uuid4().hex[:8].upper()}",
            transaction_type="ISTV",
            status="POSTED",
            transaction_date=payload.transaction_date,
            source_warehouse_id=payload.source_warehouse_id,
            destination_warehouse_id=payload.destination_warehouse_id,
            warehouse_id=payload.source_warehouse_id,
            created_by=_to_uuid(user_id),
            created_at=datetime.now(timezone.utc),
            posted_by=_to_uuid(user_id),
            posted_at=datetime.now(timezone.utc),
        )
        tx.lines = lines

        # Store TransferRecord with in-transit lines
        tr = TransferRecord(
            id=uuid4(),
            istv_transaction_id=tx_id,
            source_warehouse_id=payload.source_warehouse_id,
            destination_warehouse_id=payload.destination_warehouse_id,
            status="IN_TRANSIT",
            created_at=datetime.now(timezone.utc),
        )
        tr.lines = [
            TransferLine(
                id=uuid4(),
                transfer_record_id=tr.id,
                item_id=line.item_id,
                sent_quantity=line.quantity,
                received_quantity=Decimal("0.0000"),
            )
            for line in lines
        ]
        self.transfers[tx_id] = tr
        return tx

    async def create_and_post_istrv(self, user_id, payload: ISTRVCreate):
        tx_id = uuid4()
        lines = [
            TransactionLine(
                id=uuid4(),
                transaction_id=tx_id,
                line_number=idx,
                item_id=line.item_id,
                quantity=line.quantity,
                unit="PCS",
                remarks=line.remarks,
            )
            for idx, line in enumerate(payload.lines, start=1)
        ]
        tx = Transaction(
            id=tx_id,
            transaction_number=f"ISTRV-20260918-{uuid4().hex[:8].upper()}",
            transaction_type="ISTRV",
            status="POSTED",
            transaction_date=payload.transaction_date,
            destination_warehouse_id=payload.destination_warehouse_id,
            warehouse_id=payload.destination_warehouse_id,
            reference_transaction_id=payload.istv_transaction_id,
            created_by=_to_uuid(user_id),
            created_at=datetime.now(timezone.utc),
            posted_by=_to_uuid(user_id),
            posted_at=datetime.now(timezone.utc),
        )
        tx.lines = lines
        return tx

    async def get_transfer_record_by_istv_id(self, istv_id: UUID):
        return self.transfers.get(istv_id)


# ---------------------------------------------------------------------------
# 1. Route Registration & Authentication Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transfer_routes_are_registered():
    assert app.url_path_for("create_istv") == "/api/v1/transactions/istv"
    assert app.url_path_for("create_istrv") == "/api/v1/transactions/istrv"
    sample_id = uuid4()
    assert (
        app.url_path_for("get_transfer_record", istv_id=str(sample_id))
        == f"/api/v1/transactions/transfers/{sample_id}"
    )


@pytest.mark.asyncio
async def test_istv_requires_authentication():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/transactions/istv", json={})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_istrv_requires_authentication():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/transactions/istrv", json={})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_transfer_role_authorization(token_factory):
    """Confirms VIEWER is rejected with HTTP 403, while ADMIN, INVENTORY_MANAGER, and STORE_KEEPER can execute transfers."""
    fake_service = FakeTransferService()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service

    wh1 = str(uuid4())
    wh2 = str(uuid4())
    payload = {
        "source_warehouse_id": wh1,
        "destination_warehouse_id": wh2,
        "lines": [{"item_id": str(uuid4()), "quantity": 10.0, "unit": "PCS"}],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # VIEWER rejected with 403
        viewer_token = token_factory(role="VIEWER")
        res_viewer = await client.post(
            "/api/v1/transactions/istv",
            json=payload,
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert res_viewer.status_code == 403

        # STORE_KEEPER authorized
        sk_token = token_factory(role="STORE_KEEPER")
        res_sk = await client.post(
            "/api/v1/transactions/istv",
            json=payload,
            headers={"Authorization": f"Bearer {sk_token}"},
        )
        assert res_sk.status_code == 201

        # INVENTORY_MANAGER authorized
        im_token = token_factory(role="INVENTORY_MANAGER")
        res_im = await client.post(
            "/api/v1/transactions/istv",
            json=payload,
            headers={"Authorization": f"Bearer {im_token}"},
        )
        assert res_im.status_code == 201

        # ADMIN authorized
        admin_token = token_factory(role="ADMIN")
        res_admin = await client.post(
            "/api/v1/transactions/istv",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_admin.status_code == 201

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. Schema Validation Tests (Source != Destination & Uniqueness)
# ---------------------------------------------------------------------------


def test_istv_fails_when_source_equals_destination():
    """Confirms HTTP 400 / 422 rejection when source and destination are identical."""
    wh_id = uuid4()
    with pytest.raises(ValidationError) as exc:
        ISTVCreate(
            source_warehouse_id=wh_id,
            destination_warehouse_id=wh_id,
            lines=[
                TransactionLineCreate(
                    item_id=uuid4(), quantity=Decimal("10"), unit="PCS"
                )
            ],
        )
    assert "different" in str(exc.value).lower()


def test_istv_rejects_duplicate_items():
    item_id = uuid4()
    with pytest.raises(ValidationError) as exc:
        ISTVCreate(
            source_warehouse_id=uuid4(),
            destination_warehouse_id=uuid4(),
            lines=[
                TransactionLineCreate(item_id=item_id, quantity=Decimal("10"), unit="PCS"),
                TransactionLineCreate(item_id=item_id, quantity=Decimal("5"), unit="PCS"),
            ],
        )
    assert "duplicate item" in str(exc.value).lower()


def test_istrv_rejects_duplicate_items():
    item_id = uuid4()
    with pytest.raises(ValidationError) as exc:
        ISTRVCreate(
            istv_transaction_id=uuid4(),
            destination_warehouse_id=uuid4(),
            lines=[
                ISTRVLineCreate(item_id=item_id, quantity=Decimal("10")),
                ISTRVLineCreate(item_id=item_id, quantity=Decimal("5")),
            ],
        )
    assert "duplicate item" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# 3. ISTV Service Logic Tests (In-Transit Separation, Stock Deductions)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_istv_success():
    """Confirms source balance decrement, OUT movement, creation of TransferRecord in IN_TRANSIT status, and unchanged destination balance."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.add_all = MagicMock()
    service = TransactionService(mock_session)

    src_wh = uuid4()
    dst_wh = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    # Source balance has 100 on hand, 0 reserved
    src_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=src_wh,
        item_id=item_id,
        quantity_on_hand=Decimal("100.0000"),
        quantity_reserved=Decimal("0.0000"),
        updated_at=datetime.now(timezone.utc),
    )

    service.repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item_id: src_bal}
    )
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_transfer_record = AsyncMock()
    service.repo.create_transfer_lines = AsyncMock()
    service.repo.create_audit_log = AsyncMock()
    service.repo.get_transaction_by_id = AsyncMock(return_value=None)

    payload = ISTVCreate(
        source_warehouse_id=src_wh,
        destination_warehouse_id=dst_wh,
        plate_no="ET-3-12345",
        driver_name="Abebe Bikila",
        lines=[
            TransactionLineCreate(
                item_id=item_id, quantity=Decimal("40.0000"), unit="PCS"
            )
        ],
    )

    tx = await service.create_and_post_istv(user_id=user_id, payload=payload)

    # 1. Source balance decremented by 40
    assert src_bal.quantity_on_hand == Decimal("60.0000")

    # 2. Stock movement is OUT from source warehouse
    service.repo.create_stock_movement.assert_awaited_once()
    sm_call = service.repo.create_stock_movement.await_args[1]
    assert sm_call["warehouse_id"] == src_wh
    assert sm_call["movement_type"] == "OUT"
    assert sm_call["quantity"] == Decimal("40.0000")
    assert sm_call["running_balance"] == Decimal("60.0000")

    # 3. Transfer record created with status IN_TRANSIT
    service.repo.create_transfer_record.assert_awaited_once()
    tr_call = service.repo.create_transfer_record.await_args[0][0]
    assert tr_call.source_warehouse_id == src_wh
    assert tr_call.destination_warehouse_id == dst_wh
    assert tr_call.status == "IN_TRANSIT"
    assert tr_call.plate_no == "ET-3-12345"

    # 4. Transfer lines created with sent=40, received=0
    service.repo.create_transfer_lines.assert_awaited_once()
    tl_call = service.repo.create_transfer_lines.await_args[0][0]
    assert len(tl_call) == 1
    assert tl_call[0].sent_quantity == Decimal("40.0000")
    assert tl_call[0].received_quantity == Decimal("0.0000")
    assert tl_call[0].remaining_quantity == Decimal("40.0000")

    # 5. Audit log created
    service.repo.create_audit_log.assert_awaited_once()
    audit_call = service.repo.create_audit_log.await_args[1]
    assert audit_call["action"] == "POST_ISTV"

    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_istv_fails_when_stock_insufficient():
    """Confirms HTTP 400 rejection when requested transfer quantity exceeds available stock."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    src_wh = uuid4()
    dst_wh = uuid4()
    item_id = uuid4()

    # Source balance has only 15 on hand
    src_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=src_wh,
        item_id=item_id,
        quantity_on_hand=Decimal("15.0000"),
        quantity_reserved=Decimal("0.0000"),
        updated_at=datetime.now(timezone.utc),
    )

    service.repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item_id: src_bal}
    )

    payload = ISTVCreate(
        source_warehouse_id=src_wh,
        destination_warehouse_id=dst_wh,
        lines=[
            TransactionLineCreate(
                item_id=item_id, quantity=Decimal("30.0000"), unit="PCS"
            )
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_and_post_istv(user_id=uuid4(), payload=payload)

    assert exc.value.status_code == 400
    assert "Insufficient stock" in exc.value.detail
    mock_session.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. ISTRV Service Logic Tests (Receiving, Increments, Status Progression)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_istrv_full_receiving():
    """Confirms destination balance increment, IN movement, and status transition to COMPLETED with completed_at."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    src_wh = uuid4()
    dst_wh = uuid4()
    item_id = uuid4()
    istv_id = uuid4()
    user_id = uuid4()

    # Existing transfer record in transit for 50 units
    tr = TransferRecord(
        id=uuid4(),
        istv_transaction_id=istv_id,
        source_warehouse_id=src_wh,
        destination_warehouse_id=dst_wh,
        status="IN_TRANSIT",
        created_at=datetime.now(timezone.utc),
    )
    t_line = TransferLine(
        id=uuid4(),
        transfer_record_id=tr.id,
        item_id=item_id,
        sent_quantity=Decimal("50.0000"),
        received_quantity=Decimal("0.0000"),
    )
    tr.lines = [t_line]

    # Destination warehouse already has 10 units
    dst_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=dst_wh,
        item_id=item_id,
        quantity_on_hand=Decimal("10.0000"),
        quantity_reserved=Decimal("0.0000"),
        updated_at=datetime.now(timezone.utc),
    )

    service.repo.get_transfer_record_by_istv_id = AsyncMock(return_value=tr)
    service.repo.get_transaction_by_id = AsyncMock(return_value=None)
    service.repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item_id: dst_bal}
    )
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()
    service.repo.get_or_create_balance = AsyncMock(return_value=dst_bal)
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    # Receive full 50 units
    payload = ISTRVCreate(
        istv_transaction_id=istv_id,
        destination_warehouse_id=dst_wh,
        lines=[ISTRVLineCreate(item_id=item_id, quantity=Decimal("50.0000"))],
    )

    tx = await service.create_and_post_istrv(user_id=user_id, payload=payload)

    # 1. Destination balance increased to 60
    assert dst_bal.quantity_on_hand == Decimal("60.0000")

    # 2. Stock movement is IN to destination warehouse
    service.repo.create_stock_movement.assert_awaited_once()
    sm_call = service.repo.create_stock_movement.await_args[1]
    assert sm_call["warehouse_id"] == dst_wh
    assert sm_call["movement_type"] == "IN"
    assert sm_call["quantity"] == Decimal("50.0000")
    assert sm_call["running_balance"] == Decimal("60.0000")

    # 3. TransferLine received_quantity updated to 50
    assert t_line.received_quantity == Decimal("50.0000")
    assert t_line.remaining_quantity == Decimal("0.0000")

    # 4. Transfer status transitions to COMPLETED with completed_at set
    assert tr.status == "COMPLETED"
    assert tr.completed_at is not None

    # 5. Audit log
    service.repo.create_audit_log.assert_awaited_once()
    audit_call = service.repo.create_audit_log.await_args[1]
    assert audit_call["action"] == "POST_ISTRV"

    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_istrv_partial_receiving():
    """Confirms partial receipt updates received_quantity, keeps status as PARTIALLY_RECEIVED, and maintains accurate remaining_quantity."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    src_wh = uuid4()
    dst_wh = uuid4()
    item_id = uuid4()
    istv_id = uuid4()

    tr = TransferRecord(
        id=uuid4(),
        istv_transaction_id=istv_id,
        source_warehouse_id=src_wh,
        destination_warehouse_id=dst_wh,
        status="IN_TRANSIT",
        created_at=datetime.now(timezone.utc),
    )
    t_line = TransferLine(
        id=uuid4(),
        transfer_record_id=tr.id,
        item_id=item_id,
        sent_quantity=Decimal("100.0000"),
        received_quantity=Decimal("0.0000"),
    )
    tr.lines = [t_line]

    dst_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=dst_wh,
        item_id=item_id,
        quantity_on_hand=Decimal("0.0000"),
        quantity_reserved=Decimal("0.0000"),
        updated_at=datetime.now(timezone.utc),
    )

    service.repo.get_transfer_record_by_istv_id = AsyncMock(return_value=tr)
    service.repo.get_transaction_by_id = AsyncMock(return_value=None)
    service.repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item_id: dst_bal}
    )
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()
    service.repo.get_or_create_balance = AsyncMock(return_value=dst_bal)
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    # Receive partial 40 units out of 100
    payload = ISTRVCreate(
        istv_transaction_id=istv_id,
        destination_warehouse_id=dst_wh,
        lines=[ISTRVLineCreate(item_id=item_id, quantity=Decimal("40.0000"))],
    )

    await service.create_and_post_istrv(user_id=uuid4(), payload=payload)

    assert dst_bal.quantity_on_hand == Decimal("40.0000")
    assert t_line.received_quantity == Decimal("40.0000")
    assert t_line.remaining_quantity == Decimal("60.0000")
    assert tr.status == "PARTIALLY_RECEIVED"
    assert tr.completed_at is None


@pytest.mark.asyncio
async def test_istrv_subsequent_receiving_completes_transfer():
    """Confirms a second partial receipt completes the transfer."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    src_wh = uuid4()
    dst_wh = uuid4()
    item_id = uuid4()
    istv_id = uuid4()

    # Already partially received 40 out of 100
    tr = TransferRecord(
        id=uuid4(),
        istv_transaction_id=istv_id,
        source_warehouse_id=src_wh,
        destination_warehouse_id=dst_wh,
        status="PARTIALLY_RECEIVED",
        created_at=datetime.now(timezone.utc),
    )
    t_line = TransferLine(
        id=uuid4(),
        transfer_record_id=tr.id,
        item_id=item_id,
        sent_quantity=Decimal("100.0000"),
        received_quantity=Decimal("40.0000"),
    )
    tr.lines = [t_line]

    dst_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=dst_wh,
        item_id=item_id,
        quantity_on_hand=Decimal("40.0000"),
        quantity_reserved=Decimal("0.0000"),
        updated_at=datetime.now(timezone.utc),
    )

    service.repo.get_transfer_record_by_istv_id = AsyncMock(return_value=tr)
    service.repo.get_transaction_by_id = AsyncMock(return_value=None)
    service.repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item_id: dst_bal}
    )
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()
    service.repo.get_or_create_balance = AsyncMock(return_value=dst_bal)
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    # Receive the remaining 60 units
    payload = ISTRVCreate(
        istv_transaction_id=istv_id,
        destination_warehouse_id=dst_wh,
        lines=[ISTRVLineCreate(item_id=item_id, quantity=Decimal("60.0000"))],
    )

    await service.create_and_post_istrv(user_id=uuid4(), payload=payload)

    assert dst_bal.quantity_on_hand == Decimal("100.0000")
    assert t_line.received_quantity == Decimal("100.0000")
    assert t_line.remaining_quantity == Decimal("0.0000")
    assert tr.status == "COMPLETED"
    assert tr.completed_at is not None
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_istrv_rejects_over_receiving():
    """Confirms receipt exceeding remaining in-transit quantity is rejected with HTTP 400 (ADR-005)."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    src_wh = uuid4()
    dst_wh = uuid4()
    item_id = uuid4()
    istv_id = uuid4()

    # Sent is 50, but already received 30. Remaining is only 20!
    tr = TransferRecord(
        id=uuid4(),
        istv_transaction_id=istv_id,
        source_warehouse_id=src_wh,
        destination_warehouse_id=dst_wh,
        status="PARTIALLY_RECEIVED",
        created_at=datetime.now(timezone.utc),
    )
    t_line = TransferLine(
        id=uuid4(),
        transfer_record_id=tr.id,
        item_id=item_id,
        sent_quantity=Decimal("50.0000"),
        received_quantity=Decimal("30.0000"),
    )
    tr.lines = [t_line]

    service.repo.get_transfer_record_by_istv_id = AsyncMock(return_value=tr)

    # Attempt to receive 25 (exceeds remaining 20)
    payload = ISTRVCreate(
        istv_transaction_id=istv_id,
        destination_warehouse_id=dst_wh,
        lines=[ISTRVLineCreate(item_id=item_id, quantity=Decimal("25.0000"))],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_and_post_istrv(user_id=uuid4(), payload=payload)

    assert exc.value.status_code == 400
    assert "Remaining in-transit quantity is 20.0000" in exc.value.detail
    assert "Over-receiving is prohibited (ADR-005)" in exc.value.detail
    mock_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_istrv_fails_when_transfer_already_completed():
    """Confirms receipt on a COMPLETED transfer is rejected with HTTP 400."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    istv_id = uuid4()
    dst_wh = uuid4()

    tr = TransferRecord(
        id=uuid4(),
        istv_transaction_id=istv_id,
        source_warehouse_id=uuid4(),
        destination_warehouse_id=dst_wh,
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    tr.lines = []
    service.repo.get_transfer_record_by_istv_id = AsyncMock(return_value=tr)

    payload = ISTRVCreate(
        istv_transaction_id=istv_id,
        destination_warehouse_id=dst_wh,
        lines=[ISTRVLineCreate(item_id=uuid4(), quantity=Decimal("10.0000"))],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_and_post_istrv(user_id=uuid4(), payload=payload)

    assert exc.value.status_code == 400
    assert "already COMPLETED" in exc.value.detail


@pytest.mark.asyncio
async def test_istrv_fails_on_mismatched_destination():
    """Confirms receipt is rejected if destination warehouse does not match the transfer record."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    istv_id = uuid4()
    actual_dst_wh = uuid4()
    wrong_dst_wh = uuid4()

    tr = TransferRecord(
        id=uuid4(),
        istv_transaction_id=istv_id,
        source_warehouse_id=uuid4(),
        destination_warehouse_id=actual_dst_wh,
        status="IN_TRANSIT",
        created_at=datetime.now(timezone.utc),
    )
    tr.lines = []
    service.repo.get_transfer_record_by_istv_id = AsyncMock(return_value=tr)

    payload = ISTRVCreate(
        istv_transaction_id=istv_id,
        destination_warehouse_id=wrong_dst_wh,
        lines=[ISTRVLineCreate(item_id=uuid4(), quantity=Decimal("10.0000"))],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_and_post_istrv(user_id=uuid4(), payload=payload)

    assert exc.value.status_code == 400
    assert "does not match transfer destination" in exc.value.detail


# ---------------------------------------------------------------------------
# 5. GET /api/v1/transactions/transfers/{istv_id} Endpoint Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_transfer_record_endpoint(token_factory):
    fake_service = FakeTransferService()
    istv_id = uuid4()
    src_wh = uuid4()
    dst_wh = uuid4()
    item_id = uuid4()

    tr = TransferRecord(
        id=uuid4(),
        istv_transaction_id=istv_id,
        source_warehouse_id=src_wh,
        destination_warehouse_id=dst_wh,
        status="IN_TRANSIT",
        created_at=datetime.now(timezone.utc),
    )
    tl = TransferLine(
        id=uuid4(),
        transfer_record_id=tr.id,
        item_id=item_id,
        sent_quantity=Decimal("30.0000"),
        received_quantity=Decimal("0.0000"),
    )
    tr.lines = [tl]
    fake_service.transfers[istv_id] = tr

    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role="VIEWER")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/v1/transactions/transfers/{istv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "IN_TRANSIT"
    assert len(data["lines"]) == 1
    assert Decimal(str(data["lines"][0]["remaining_quantity"])) == Decimal("30.0000")


@pytest.mark.asyncio
async def test_get_transfer_record_not_found(token_factory):
    fake_service = FakeTransferService()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role="VIEWER")
    missing_id = uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/v1/transactions/transfers/{missing_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
