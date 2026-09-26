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
from app.models.transaction import StockMovement, Transaction, TransactionLine
from app.repositories.transaction import TransactionRepository
from app.schemas.transaction import (
    GRVCreate,
    SIVCreate,
    TransactionLineCreate,
    TransactionRead,
)
from app.services.transaction import (
    TransactionService,
    _to_uuid,
    generate_transaction_number,
)


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
        self.grv_calls = []
        self.siv_calls = []

    async def create_and_post_grv(self, user_id, payload: GRVCreate):
        self.grv_calls.append((user_id, payload))
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
            transaction_number=f"GRV-20260918-{uuid4().hex[:8].upper()}",
            transaction_type="GRV",
            status="POSTED",
            transaction_date=payload.transaction_date,
            warehouse_id=payload.warehouse_id,
            project_id=payload.project_id,
            supplier_name=payload.supplier_name,
            invoice_no=payload.invoice_no,
            received_grv_no=payload.received_grv_no,
            store_no=payload.store_no,
            remarks=payload.remarks,
            created_by=_to_uuid(user_id),
            created_at=datetime.now(timezone.utc),
            posted_by=_to_uuid(user_id),
            posted_at=datetime.now(timezone.utc),
        )
        tx.lines = lines
        return tx

    async def create_and_post_siv(self, user_id, payload: SIVCreate):
        self.siv_calls.append((user_id, payload))
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
            transaction_number=f"SIV-20260918-{uuid4().hex[:8].upper()}",
            transaction_type="SIV",
            status="POSTED",
            transaction_date=payload.transaction_date,
            warehouse_id=payload.warehouse_id,
            project_id=payload.project_id,
            requested_from=payload.requested_from,
            project_dept=payload.project_dept,
            requested_no=payload.requested_no,
            siv_no=payload.siv_no,
            material_summary=payload.material_summary,
            issued_by_name=payload.issued_by_name,
            checked_by_name=payload.checked_by_name,
            received_by_name=payload.received_by_name,
            approved_by_name=payload.approved_by_name,
            remarks=payload.remarks,
            created_by=_to_uuid(user_id),
            created_at=datetime.now(timezone.utc),
            posted_by=_to_uuid(user_id),
            posted_at=datetime.now(timezone.utc),
        )
        tx.lines = lines
        return tx

    async def list_transactions(self, transaction_type=None, warehouse_id=None, search=None, skip=0, limit=50):
        return []


# ---------------------------------------------------------------------------
# 1. Route Registration and Authentication Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transaction_routes_are_registered():
    assert app.url_path_for("create_grv") == "/api/v1/transactions/grv"
    assert app.url_path_for("create_siv") == "/api/v1/transactions/siv"
    assert app.url_path_for("list_transactions") == "/api/v1/transactions"
    sample_id = uuid4()
    assert (
        app.url_path_for("get_transaction", transaction_id=str(sample_id))
        == f"/api/v1/transactions/{sample_id}"
    )



@pytest.mark.asyncio
async def test_grv_requires_authentication():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/transactions/grv", json={})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_siv_requires_authentication():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/transactions/siv", json={})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER"])
async def test_grv_authorized_roles_succeed(token_factory, role):
    fake_service = FakeTransactionService()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role=role)
    payload = {
        "warehouse_id": str(uuid4()),
        "supplier_name": "Acme Supplier",
        "lines": [{"item_id": str(uuid4()), "quantity": 10.5, "unit": "PCS"}],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/transactions/grv",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 201
    data = response.json()
    assert data["transaction_type"] == "GRV"
    assert data["status"] == "POSTED"
    assert len(data["lines"]) == 1
    assert Decimal(str(data["lines"][0]["quantity"])) == Decimal("10.5")


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER"])
async def test_siv_authorized_roles_succeed(token_factory, role):
    fake_service = FakeTransactionService()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role=role)
    payload = {
        "warehouse_id": str(uuid4()),
        "requested_from": "Construction Site A",
        "lines": [{"item_id": str(uuid4()), "quantity": 5.0, "unit": "BAG"}],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/transactions/siv",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 201
    data = response.json()
    assert data["transaction_type"] == "SIV"
    assert data["status"] == "POSTED"
    assert len(data["lines"]) == 1


@pytest.mark.asyncio
async def test_grv_viewer_role_is_forbidden(token_factory):
    fake_service = FakeTransactionService()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role="VIEWER")
    payload = {
        "warehouse_id": str(uuid4()),
        "lines": [{"item_id": str(uuid4()), "quantity": 10.0, "unit": "PCS"}],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/transactions/grv",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_siv_viewer_role_is_forbidden(token_factory):
    fake_service = FakeTransactionService()
    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role="VIEWER")
    payload = {
        "warehouse_id": str(uuid4()),
        "lines": [{"item_id": str(uuid4()), "quantity": 5.0, "unit": "BAG"}],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/transactions/siv",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_transaction_by_id(token_factory):
    fake_service = FakeTransactionService()
    sample_id = uuid4()
    mock_tx = Transaction(
        id=sample_id,
        transaction_number="GRV-20260918-ABC12345",
        transaction_type="GRV",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=uuid4(),
        created_by=uuid4(),
        created_at=datetime.now(timezone.utc),
    )
    mock_tx.lines = []
    fake_service.repo = MagicMock()
    fake_service.repo.get_transaction_by_id = AsyncMock(return_value=mock_tx)

    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role="VIEWER")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/v1/transactions/{sample_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["transaction_number"] == "GRV-20260918-ABC12345"


@pytest.mark.asyncio
async def test_list_transactions_endpoint(token_factory):
    fake_service = FakeTransactionService()
    sample_id = uuid4()
    mock_tx = Transaction(
        id=sample_id,
        transaction_number="GRV-20260918-ABC12345",
        transaction_type="GRV",
        status="POSTED",
        transaction_date=date.today(),
        warehouse_id=uuid4(),
        created_by=uuid4(),
        created_at=datetime.now(timezone.utc),
    )
    mock_tx.lines = []
    fake_service.list_transactions = AsyncMock(return_value=[mock_tx])

    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role="VIEWER")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/transactions?transaction_type=GRV",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["transaction_number"] == "GRV-20260918-ABC12345"
    assert items[0]["transaction_type"] == "GRV"


@pytest.mark.asyncio
async def test_get_transaction_not_found(token_factory):
    fake_service = FakeTransactionService()
    fake_service.repo = MagicMock()
    fake_service.repo.get_transaction_by_id = AsyncMock(return_value=None)

    app.dependency_overrides[get_transaction_service] = lambda: fake_service
    token = token_factory(role="VIEWER")
    sample_id = uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/v1/transactions/{sample_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------

# 2. Pydantic Schema Validation Tests (ADR-006 & Quantities)
# ---------------------------------------------------------------------------


def test_grv_rejects_duplicate_items():
    wh_id = uuid4()
    item_id = uuid4()
    with pytest.raises(ValidationError) as exc:
        GRVCreate(
            warehouse_id=wh_id,
            lines=[
                TransactionLineCreate(item_id=item_id, quantity=Decimal("10"), unit="PCS"),
                TransactionLineCreate(item_id=item_id, quantity=Decimal("5"), unit="PCS"),
            ],
        )
    assert "Duplicate item in transaction lines is not allowed" in str(exc.value)


def test_siv_rejects_duplicate_items():
    wh_id = uuid4()
    item_id = uuid4()
    with pytest.raises(ValidationError) as exc:
        SIVCreate(
            warehouse_id=wh_id,
            lines=[
                TransactionLineCreate(item_id=item_id, quantity=Decimal("2"), unit="KG"),
                TransactionLineCreate(item_id=item_id, quantity=Decimal("3"), unit="KG"),
            ],
        )
    assert "Duplicate item in transaction lines is not allowed" in str(exc.value)


def test_transaction_line_rejects_non_positive_quantity():
    item_id = uuid4()
    with pytest.raises(ValidationError):
        TransactionLineCreate(item_id=item_id, quantity=Decimal("0"), unit="PCS")

    with pytest.raises(ValidationError):
        TransactionLineCreate(item_id=item_id, quantity=Decimal("-5"), unit="PCS")


def test_transaction_rejects_empty_lines():
    wh_id = uuid4()
    with pytest.raises(ValidationError):
        GRVCreate(warehouse_id=wh_id, lines=[])

    with pytest.raises(ValidationError):
        SIVCreate(warehouse_id=wh_id, lines=[])


@pytest.mark.asyncio
async def test_api_rejects_duplicate_items_and_negative_quantity(token_factory):
    token = token_factory(role="ADMIN")
    wh_id = str(uuid4())
    item_id = str(uuid4())

    # Duplicate items
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res1 = await client.post(
            "/api/v1/transactions/grv",
            json={
                "warehouse_id": wh_id,
                "lines": [
                    {"item_id": item_id, "quantity": 10, "unit": "PCS"},
                    {"item_id": item_id, "quantity": 5, "unit": "PCS"},
                ],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res1.status_code == 422

    # Negative quantity
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res2 = await client.post(
            "/api/v1/transactions/grv",
            json={
                "warehouse_id": wh_id,
                "lines": [{"item_id": item_id, "quantity": -5, "unit": "PCS"}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res2.status_code == 422


# ---------------------------------------------------------------------------
# 3. TransactionService GRV Atomic Posting Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_grv_creates_balance_and_in_movement():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    # Mock repo methods
    service.repo.lock_inventory_balances_for_update = AsyncMock(return_value={})
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()

    # Balance starts fresh
    new_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("0.0000"),
        quantity_reserved=Decimal("0.0000"),
        updated_at=datetime.now(timezone.utc),
    )
    service.repo.get_or_create_balance = AsyncMock(return_value=new_bal)
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()
    service.repo.get_transaction_by_id = AsyncMock(return_value=None)

    payload = GRVCreate(
        warehouse_id=wh_id,
        supplier_name="Steel Supplier Co.",
        lines=[
            TransactionLineCreate(
                item_id=item_id, quantity=Decimal("150.0000"), unit="PCS"
            )
        ],
    )

    tx = await service.create_and_post_grv(user_id=user_id, payload=payload)

    assert tx.transaction_type == "GRV"
    assert tx.status == "POSTED"
    assert tx.warehouse_id == wh_id
    assert new_bal.quantity_on_hand == Decimal("150.0000")

    # Verify stock movement IN
    service.repo.create_stock_movement.assert_awaited_once()
    sm_call = service.repo.create_stock_movement.await_args[1]
    assert sm_call["movement_type"] == "IN"
    assert sm_call["quantity"] == Decimal("150.0000")
    assert sm_call["running_balance"] == Decimal("150.0000")

    # Verify audit log
    service.repo.create_audit_log.assert_awaited_once()
    audit_call = service.repo.create_audit_log.await_args[1]
    assert audit_call["action"] == "POST_GRV"
    assert audit_call["entity_type"] == "TRANSACTION"

    # Verify commit
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_grv_increments_existing_balance():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    existing_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("50.0000"),
        quantity_reserved=Decimal("0.0000"),
        updated_at=datetime.now(timezone.utc),
    )

    service.repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item_id: existing_bal}
    )
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()
    service.repo.get_or_create_balance = AsyncMock(return_value=existing_bal)
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()
    service.repo.get_transaction_by_id = AsyncMock(return_value=None)

    payload = GRVCreate(
        warehouse_id=wh_id,
        lines=[
            TransactionLineCreate(
                item_id=item_id, quantity=Decimal("75.0000"), unit="PCS"
            )
        ],
    )

    tx = await service.create_and_post_grv(user_id=user_id, payload=payload)

    assert existing_bal.quantity_on_hand == Decimal("125.0000")
    sm_call = service.repo.create_stock_movement.await_args[1]
    assert sm_call["running_balance"] == Decimal("125.0000")
    mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. TransactionService SIV Atomic Posting & Stock Validation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_siv_decrements_balance_and_creates_out_movement():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    existing_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("100.0000"),
        quantity_reserved=Decimal("10.0000"),
        updated_at=datetime.now(timezone.utc),
    )

    service.repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item_id: existing_bal}
    )
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()
    service.repo.create_stock_movement = AsyncMock()
    service.repo.create_audit_log = AsyncMock()
    service.repo.get_transaction_by_id = AsyncMock(return_value=None)

    # Request 40 units (available is 100 - 10 = 90 >= 40)
    payload = SIVCreate(
        warehouse_id=wh_id,
        requested_from="Maintenance Team",
        lines=[
            TransactionLineCreate(
                item_id=item_id, quantity=Decimal("40.0000"), unit="PCS"
            )
        ],
    )

    tx = await service.create_and_post_siv(user_id=user_id, payload=payload)

    assert tx.transaction_type == "SIV"
    assert tx.status == "POSTED"
    assert existing_bal.quantity_on_hand == Decimal("60.0000")

    # Verify OUT movement
    service.repo.create_stock_movement.assert_awaited_once()
    sm_call = service.repo.create_stock_movement.await_args[1]
    assert sm_call["movement_type"] == "OUT"
    assert sm_call["quantity"] == Decimal("40.0000")
    assert sm_call["running_balance"] == Decimal("60.0000")

    # Verify audit log
    service.repo.create_audit_log.assert_awaited_once()
    audit_call = service.repo.create_audit_log.await_args[1]
    assert audit_call["action"] == "POST_SIV"

    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_siv_fails_when_stock_insufficient():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    # Balance has only 25 on hand, 0 reserved
    existing_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("25.0000"),
        quantity_reserved=Decimal("0.0000"),
        updated_at=datetime.now(timezone.utc),
    )

    service.repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item_id: existing_bal}
    )

    # Request 50 units (exceeds 25)
    payload = SIVCreate(
        warehouse_id=wh_id,
        lines=[
            TransactionLineCreate(
                item_id=item_id, quantity=Decimal("50.0000"), unit="PCS"
            )
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_and_post_siv(user_id=user_id, payload=payload)

    assert exc.value.status_code == 400
    assert "Insufficient stock" in exc.value.detail
    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_siv_fails_when_item_not_in_warehouse():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    # No balance record returned
    service.repo.lock_inventory_balances_for_update = AsyncMock(return_value={})

    payload = SIVCreate(
        warehouse_id=wh_id,
        lines=[
            TransactionLineCreate(
                item_id=item_id, quantity=Decimal("10.0000"), unit="PCS"
            )
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_and_post_siv(user_id=user_id, payload=payload)

    assert exc.value.status_code == 400
    assert "Insufficient stock" in exc.value.detail
    mock_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_siv_accounts_for_reserved_quantity():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    # On hand is 100, but 80 is reserved. Available is only 20!
    existing_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=wh_id,
        item_id=item_id,
        quantity_on_hand=Decimal("100.0000"),
        quantity_reserved=Decimal("80.0000"),
        updated_at=datetime.now(timezone.utc),
    )
    service.repo.lock_inventory_balances_for_update = AsyncMock(
        return_value={item_id: existing_bal}
    )

    # Request 30 (available is 20)
    payload = SIVCreate(
        warehouse_id=wh_id,
        lines=[
            TransactionLineCreate(
                item_id=item_id, quantity=Decimal("30.0000"), unit="PCS"
            )
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_and_post_siv(user_id=user_id, payload=payload)

    assert exc.value.status_code == 400
    assert "Available: 20.0000" in exc.value.detail
    mock_session.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5. Atomicity & Rollback Verification Tests (ADR-001)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_rollback_on_unexpected_error():
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    wh_id = uuid4()
    item_id = uuid4()
    user_id = uuid4()

    service.repo.lock_inventory_balances_for_update = AsyncMock(
        side_effect=RuntimeError("Database lock connection lost")
    )

    payload = GRVCreate(
        warehouse_id=wh_id,
        lines=[
            TransactionLineCreate(
                item_id=item_id, quantity=Decimal("10.0000"), unit="PCS"
            )
        ],
    )

    with pytest.raises(RuntimeError) as exc:
        await service.create_and_post_grv(user_id=user_id, payload=payload)

    assert "Database lock connection lost" in str(exc.value)
    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# 6. Repository Logic & Sign Checks Tests (ADR-003, ADR-004)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repository_creates_movement_with_strict_signs():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    repo = TransactionRepository(mock_session)

    tx_id = uuid4()
    line_id = uuid4()
    item_id = uuid4()
    wh_id = uuid4()

    # IN movement
    mov_in = await repo.create_stock_movement(
        transaction_id=tx_id,
        transaction_line_id=line_id,
        item_id=item_id,
        warehouse_id=wh_id,
        project_id=None,
        movement_type="IN",
        quantity=Decimal("50.0000"),
        running_balance=Decimal("50.0000"),
        movement_date=date.today(),
    )
    assert mov_in.movement_type == "IN"
    assert mov_in.quantity == Decimal("50.0000")
    assert mov_in.signed_quantity == Decimal("50.0000")
    assert mov_in.signed_quantity > 0

    # OUT movement
    mov_out = await repo.create_stock_movement(
        transaction_id=tx_id,
        transaction_line_id=line_id,
        item_id=item_id,
        warehouse_id=wh_id,
        project_id=None,
        movement_type="OUT",
        quantity=Decimal("30.0000"),
        running_balance=Decimal("20.0000"),
        movement_date=date.today(),
    )
    assert mov_out.movement_type == "OUT"
    assert mov_out.quantity == Decimal("30.0000")
    assert mov_out.signed_quantity == Decimal("-30.0000")
    assert mov_out.signed_quantity < 0


def test_transaction_number_generator():
    d = date(2026, 9, 18)
    num1 = generate_transaction_number("GRV", d)
    num2 = generate_transaction_number("SIV", d)

    assert num1.startswith("GRV-20260918-")
    assert num2.startswith("SIV-20260918-")
    assert num1 != num2
