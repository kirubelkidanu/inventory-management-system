import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock
import uuid
from datetime import datetime

from app.main import app
from app.models.user import User
from app.schemas.inventory import (
    InventoryBalanceRead,
    StockMovementRead,
    ReconciliationData,
)
from app.dependencies import get_db


# --- Mock User ---
class MockUser(User):
    def __init__(self, id: uuid.UUID, email: str, full_name: str, role: str):
        self.id = id
        self.email = email
        self.full_name = full_name
        self.role = role


# --- Mock Dependencies ---
def mock_get_db():
    db_mock = MagicMock(spec=Session)

    mock_query = MagicMock()
    mock_filter = MagicMock()
    mock_first = MagicMock()
    mock_all = MagicMock()

    mock_query.filter.return_value = mock_filter
    mock_filter.first.return_value = mock_first
    mock_filter.all.return_value = mock_all

    db_mock.query.return_value = mock_query

    yield db_mock


def mock_get_current_user_authenticated():
    return MockUser(
        id=uuid.uuid4(),
        email="test@example.com",
        full_name="Test User",
        role="VIEWER",
    )


def mock_get_current_user_unauthenticated():
    return None


# --- Test Client ---
client = TestClient(app)


# --- Test Data Setup ---
def create_mock_inventory_data(db_session_mock):
    mock_warehouse_id = uuid.uuid4()
    mock_item_id = uuid.uuid4()

    # ---------------------------------------------------------
    # Mock InventoryBalance
    # ---------------------------------------------------------
    mock_balance_obj = MagicMock()
    mock_balance_obj.warehouse_id = mock_warehouse_id
    mock_balance_obj.item_id = mock_item_id
    mock_balance_obj.quantity_on_hand = 100.0
    mock_balance_obj.quantity_reserved = 10.0
    mock_balance_obj.id = uuid.uuid4()

    mock_balance_read = InventoryBalanceRead(
        warehouse_id=mock_warehouse_id,
        item_id=mock_item_id,
        quantity_on_hand=100.0,
        quantity_reserved=10.0,
    )

    # ---------------------------------------------------------
    # Mock StockMovement #1
    # ---------------------------------------------------------
    mock_movement1_obj = MagicMock()

    mock_movement1_obj.id = uuid.uuid4()
    mock_movement1_obj.transaction_id = uuid.uuid4()
    mock_movement1_obj.transaction_line_id = uuid.uuid4()
    mock_movement1_obj.project_id = uuid.uuid4()

    mock_movement1_obj.warehouse_id = mock_warehouse_id
    mock_movement1_obj.item_id = mock_item_id

    mock_movement1_obj.quantity = 50.0
    mock_movement1_obj.signed_quantity = 50.0
    mock_movement1_obj.running_balance = 50.0

    mock_movement1_obj.notes = None
    mock_movement1_obj.movement_type = "RECEIPT"
    mock_movement1_obj.movement_date = datetime.utcnow().date()
    mock_movement1_obj.created_at = datetime.utcnow()

    # ---------------------------------------------------------
    # Mock StockMovement #2
    # ---------------------------------------------------------
    mock_movement2_obj = MagicMock()

    mock_movement2_obj.id = uuid.uuid4()
    mock_movement2_obj.transaction_id = uuid.uuid4()
    mock_movement2_obj.transaction_line_id = uuid.uuid4()
    mock_movement2_obj.project_id = uuid.uuid4()

    mock_movement2_obj.warehouse_id = mock_warehouse_id
    mock_movement2_obj.item_id = mock_item_id

    mock_movement2_obj.quantity = 20.0
    mock_movement2_obj.signed_quantity = -20.0
    mock_movement2_obj.running_balance = 30.0

    mock_movement2_obj.notes = None
    mock_movement2_obj.movement_type = "ISSUE"
    mock_movement2_obj.movement_date = datetime.utcnow().date()
    mock_movement2_obj.created_at = datetime.utcnow()

    # ---------------------------------------------------------
    # Convert mocked ORM objects to Pydantic schemas
    # ---------------------------------------------------------
    mock_movement1_read = StockMovementRead.model_validate(
        mock_movement1_obj
    )

    mock_movement2_read = StockMovementRead.model_validate(
        mock_movement2_obj
    )

    # ---------------------------------------------------------
    # Mock Reconciliation Data
    # ---------------------------------------------------------
    mock_reconciliation_item = ReconciliationData(
        warehouse_id=mock_warehouse_id,
        warehouse_code="WH001",
        warehouse_name="Warehouse 1",
        item_id=mock_item_id,
        item_code="ITEM001",
        item_description="Test Item",
        projected_balance=100.0,
        ledger_cumulative_balance=80.0,
        discrepancy=20.0,
    )

    # ---------------------------------------------------------
    # Mock InventoryService
    # ---------------------------------------------------------
    mock_inventory_service = MagicMock()

    mock_inventory_service.get_inventory_balance.return_value = (
        mock_balance_read
    )

    mock_inventory_service.get_all_balances.return_value = [
        mock_balance_read
    ]

    mock_inventory_service.get_stock_movements.return_value = [
        mock_movement1_read,
        mock_movement2_read,
    ]

    mock_inventory_service.get_reconciliation_data.return_value = [
        mock_reconciliation_item
    ]

    return {
        "warehouse_id": mock_warehouse_id,
        "item_id": mock_item_id,
        "balance_obj": mock_balance_obj,
        "balance_read": mock_balance_read,
        "movements_obj": [
            mock_movement1_obj,
            mock_movement2_obj,
        ],
        "movements_read": [
            mock_movement1_read,
            mock_movement2_read,
        ],
        "reconciliation_data": [
            mock_reconciliation_item
        ],
        "mock_inventory_service": mock_inventory_service,
    }


# ============================================================
# GET /api/v1/inventory/stock-movements
# ============================================================

# --- Unauthenticated ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_unauthenticated(),
)
def test_get_stock_movements_unauthenticated(mock_db_session):
    response = client.get(
        "/api/v1/inventory/stock-movements"
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Not authenticated"
    }


# --- No filters ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_stock_movements_no_filters(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_stock_movements.return_value = (
        mock_data["movements_read"]
    )

    response = client.get(
        "/api/v1/inventory/stock-movements"
    )

    assert response.status_code == 200
    assert response.json() == [
        m.model_dump(mode="json")
        for m in mock_data["movements_read"]
    ]


# --- Filter by warehouse ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_stock_movements_by_warehouse_id(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_stock_movements.return_value = (
        mock_data["movements_read"]
    )

    response = client.get(
        f"/api/v1/inventory/stock-movements"
        f"?warehouse_id={mock_data['warehouse_id']}"
    )

    assert response.status_code == 200
    assert response.json() == [
        m.model_dump(mode="json")
        for m in mock_data["movements_read"]
    ]


# --- Filter by item ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_stock_movements_by_item_id(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_stock_movements.return_value = (
        mock_data["movements_read"]
    )

    response = client.get(
        f"/api/v1/inventory/stock-movements"
        f"?item_id={mock_data['item_id']}"
    )

    assert response.status_code == 200
    assert response.json() == [
        m.model_dump(mode="json")
        for m in mock_data["movements_read"]
    ]


# --- Filter by warehouse + item ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_stock_movements_by_warehouse_and_item_id(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_stock_movements.return_value = (
        mock_data["movements_read"]
    )

    response = client.get(
        f"/api/v1/inventory/stock-movements"
        f"?warehouse_id={mock_data['warehouse_id']}"
        f"&item_id={mock_data['item_id']}"
    )

    assert response.status_code == 200
    assert response.json() == [
        m.model_dump(mode="json")
        for m in mock_data["movements_read"]
    ]


# --- No results ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_stock_movements_no_results(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_stock_movements.return_value = []

    response = client.get(
        f"/api/v1/inventory/stock-movements"
        f"?warehouse_id={uuid.uuid4()}"
        f"&item_id={uuid.uuid4()}"
    )

    assert response.status_code == 200
    assert response.json() == []


# ============================================================
# GET /api/v1/inventory/reconciliation
# ============================================================

# --- Unauthenticated ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_unauthenticated(),
)
def test_get_reconciliation_unauthenticated(
    mock_db_session,
):
    response = client.get(
        "/api/v1/inventory/reconciliation"
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Not authenticated"
    }


# --- Data found ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_reconciliation_data_found(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_reconciliation_data.return_value = (
        mock_data["reconciliation_data"]
    )

    response = client.get(
        "/api/v1/inventory/reconciliation"
    )

    assert response.status_code == 200
    assert response.json() == [
        r.model_dump(mode="json")
        for r in mock_data["reconciliation_data"]
    ]


# --- No results ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_reconciliation_data_no_results(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_reconciliation_data.return_value = []

    response = client.get(
        "/api/v1/inventory/reconciliation"
    )

    assert response.status_code == 200
    assert response.json() == []


# ============================================================
# GET /api/v1/inventory/balances
# ============================================================

# --- Unauthenticated ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_unauthenticated(),
)
def test_get_inventory_balances_collection_unauthenticated(
    mock_db_session,
):
    response = client.get(
        "/api/v1/inventory/balances"
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Not authenticated"
    }


# --- No filters ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_inventory_balances_collection_no_filters(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_all_balances.return_value = [
        mock_data["balance_read"]
    ]

    response = client.get(
        "/api/v1/inventory/balances"
    )

    assert response.status_code == 200
    assert response.json() == [
        mock_data["balance_read"].model_dump(mode="json")
    ]


# --- Filter by warehouse ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_inventory_balances_collection_by_warehouse_id(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_all_balances.return_value = [
        mock_data["balance_read"]
    ]

    response = client.get(
        f"/api/v1/inventory/balances"
        f"?warehouse_id={mock_data['warehouse_id']}"
    )

    assert response.status_code == 200
    assert response.json() == [
        mock_data["balance_read"].model_dump(mode="json")
    ]


# --- Filter by item ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_inventory_balances_collection_by_item_id(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_all_balances.return_value = [
        mock_data["balance_read"]
    ]

    response = client.get(
        f"/api/v1/inventory/balances"
        f"?item_id={mock_data['item_id']}"
    )

    assert response.status_code == 200
    assert response.json() == [
        mock_data["balance_read"].model_dump(mode="json")
    ]


# --- Filter by warehouse + item ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_inventory_balances_collection_by_warehouse_and_item_id(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_all_balances.return_value = [
        mock_data["balance_read"]
    ]

    response = client.get(
        f"/api/v1/inventory/balances"
        f"?warehouse_id={mock_data['warehouse_id']}"
        f"&item_id={mock_data['item_id']}"
    )

    assert response.status_code == 200
    assert response.json() == [
        mock_data["balance_read"].model_dump(mode="json")
    ]


# ============================================================
# GET /api/v1/inventory/balances/{warehouse_id}/{item_id}
# ============================================================

# --- Unauthenticated ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_unauthenticated(),
)
def test_get_inventory_balance_specific_unauthenticated(
    mock_db_session,
):
    warehouse_id = uuid.uuid4()
    item_id = uuid.uuid4()

    response = client.get(
        f"/api/v1/inventory/balances/"
        f"{warehouse_id}/{item_id}"
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Not authenticated"
    }


# --- Found ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_inventory_balance_specific_found(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_inventory_balance.return_value = (
        mock_data["balance_read"]
    )

    response = client.get(
        f"/api/v1/inventory/balances/"
        f"{mock_data['warehouse_id']}/"
        f"{mock_data['item_id']}"
    )

    assert response.status_code == 200
    assert response.json() == (
        mock_data["balance_read"].model_dump(mode="json")
    )


# --- Not found ---
@patch(
    "app.dependencies.get_current_user",
    return_value=mock_get_current_user_authenticated(),
)
@patch("app.api.routes.inventory.InventoryService")
def test_get_inventory_balance_specific_not_found(
    MockInventoryService,
    mock_db_session,
):
    mock_data = create_mock_inventory_data(
        mock_db_session
    )

    mock_inventory_service_instance = (
        MockInventoryService.return_value
    )

    mock_inventory_service_instance.get_inventory_balance.return_value = None

    response = client.get(
        f"/api/v1/inventory/balances/"
        f"{mock_data['warehouse_id']}/"
        f"{mock_data['item_id']}"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Inventory balance not found for the specified "
            "warehouse and item."
        )
    }


# ============================================================
# Override app dependencies for tests
# ============================================================

app.dependency_overrides[get_db] = mock_get_db


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def mock_db_session():
    db_session_mock = next(mock_get_db())
    yield db_session_mock