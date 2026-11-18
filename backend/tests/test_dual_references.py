from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.models.transaction import (
    Transaction,
    TransferRecord,
    TransferLine,
)
from app.models.inventory import InventoryBalance
from app.schemas.transaction import (
    ISTVCreate,
    ISTRVCreate,
    TransactionLineCreate,
    ISTRVLineCreate,
)
from app.services.transaction import TransactionService
from app.services.report import ReportService


@pytest.mark.asyncio
async def test_istv_dual_reference_persistence():
    """Verify ISTV persists both istv_no and invoice_no."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    src_wh = uuid4()
    dst_wh = uuid4()
    item_id = uuid4()
    user_id = uuid4()

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
    service.repo.get_latest_inbound_unit_price = AsyncMock(return_value=Decimal("50.0000"))

    payload = ISTVCreate(
        source_warehouse_id=src_wh,
        destination_warehouse_id=dst_wh,
        istv_no="ISTV-VOUCHER-001",
        invoice_no="WB-WAYBILL-999",
        plate_no="ET-3-9999",
        driver_name="Chala Tufa",
        lines=[
            TransactionLineCreate(
                item_id=item_id, quantity=Decimal("20.0000"), unit="PCS"
            )
        ],
    )

    await service.create_and_post_istv(user_id=user_id, payload=payload)

    # Assert create_transaction called with both istv_no and invoice_no
    service.repo.create_transaction.assert_awaited_once()
    created_tx = service.repo.create_transaction.await_args[0][0]
    assert created_tx.istv_no == "ISTV-VOUCHER-001"
    assert created_tx.invoice_no == "WB-WAYBILL-999"


@pytest.mark.asyncio
async def test_istrv_dual_reference_and_invoice_inheritance():
    """Verify ISTRV persists istrv_no and inherits parent ISTV invoice_no if omitted."""
    mock_session = AsyncMock()
    service = TransactionService(mock_session)

    src_wh = uuid4()
    dst_wh = uuid4()
    item_id = uuid4()
    user_id = uuid4()
    istv_tx_id = uuid4()

    # Mock parent ISTV transaction with invoice_no
    parent_istv = Transaction(
        id=istv_tx_id,
        transaction_number="ISTV-202611-0001",
        transaction_type="ISTV",
        status="POSTED",
        transaction_date=datetime.now(timezone.utc).date(),
        source_warehouse_id=src_wh,
        destination_warehouse_id=dst_wh,
        istv_no="ISTV-ORIG-REF",
        invoice_no="PARENT-INV-777",
    )

    # Mock active transfer record
    tr = TransferRecord(
        id=uuid4(),
        istv_transaction_id=istv_tx_id,
        source_warehouse_id=src_wh,
        destination_warehouse_id=dst_wh,
        status="IN_TRANSIT",
        created_at=datetime.now(timezone.utc),
    )
    tl = TransferLine(
        id=uuid4(),
        transfer_record_id=tr.id,
        item_id=item_id,
        sent_quantity=Decimal("50.0000"),
        received_quantity=Decimal("0.0000"),
    )
    tr.lines = [tl]

    dst_bal = InventoryBalance(
        id=uuid4(),
        warehouse_id=dst_wh,
        item_id=item_id,
        quantity_on_hand=Decimal("0.0000"),
        quantity_reserved=Decimal("0.0000"),
        updated_at=datetime.now(timezone.utc),
    )

    service.repo.get_transfer_record_by_istv_id = AsyncMock(return_value=tr)
    service.repo.get_transaction_by_id = AsyncMock(return_value=parent_istv)
    service.repo.lock_inventory_balances_for_update = AsyncMock(return_value={})
    service.repo.get_or_create_balance = AsyncMock(return_value=dst_bal)
    service.repo.create_inventory_balance = AsyncMock()
    service.repo.create_transaction = AsyncMock()
    service.repo.create_transaction_lines = AsyncMock()
    service.repo.create_stock_movement = AsyncMock()
    service.repo.update_transfer_record_status = AsyncMock()
    service.repo.create_audit_log = AsyncMock()

    # Case A: Omit invoice_no -> should inherit parent_istv.invoice_no
    payload_inherit = ISTRVCreate(
        istv_transaction_id=istv_tx_id,
        destination_warehouse_id=dst_wh,
        istrv_no="ISTRV-RCV-888",
        lines=[
            ISTRVLineCreate(item_id=item_id, quantity=Decimal("50.0000"))
        ],
    )

    await service.create_and_post_istrv(user_id=user_id, payload=payload_inherit)
    created_istrv_1 = service.repo.create_transaction.await_args[0][0]
    assert created_istrv_1.istrv_no == "ISTRV-RCV-888"
    assert created_istrv_1.invoice_no == "PARENT-INV-777"

    # Case B: Explicit invoice_no -> should override parent invoice_no
    service.repo.create_transaction.reset_mock()
    tr.status = "IN_TRANSIT"
    tl.received_quantity = Decimal("0.0000")
    payload_explicit = ISTRVCreate(
        istv_transaction_id=istv_tx_id,
        destination_warehouse_id=dst_wh,
        istrv_no="ISTRV-RCV-999",
        invoice_no="CUSTOM-RCV-INV-111",
        lines=[
            ISTRVLineCreate(item_id=item_id, quantity=Decimal("50.0000"))
        ],
    )

    await service.create_and_post_istrv(user_id=user_id, payload=payload_explicit)
    created_istrv_2 = service.repo.create_transaction.await_args[0][0]
    assert created_istrv_2.istrv_no == "ISTRV-RCV-999"
    assert created_istrv_2.invoice_no == "CUSTOM-RCV-INV-111"


def test_trial_balance_reference_resolution():
    """Verify ReportService._resolve_reference_number prioritizes invoice, voucher ref, etc."""
    service = ReportService(MagicMock())
    # Row with both voucher ref and invoice -> resolves primary reference
    grv_row = {
        "transaction_type": "GRV",
        "received_grv_no": "V-GRV-001",
        "invoice_no": "INV-SUP-101",
    }
    assert service._resolve_reference_number(grv_row) == "INV-SUP-101"

    # SIV row with siv_no and requested_no
    siv_row = {
        "transaction_type": "SIV",
        "siv_no": "SIV-777",
        "requested_no": "REQ-123",
    }
    assert service._resolve_reference_number(siv_row) == "SIV-777"

    # ISTV row with only istv_no
    istv_row = {
        "transaction_type": "ISTV",
        "istv_no": "ISTV-REF-50",
    }
    assert service._resolve_reference_number(istv_row) == "ISTV-REF-50"

    # ISTRV row with only istrv_no
    istrv_row = {
        "transaction_type": "ISTRV",
        "istrv_no": "ISTRV-REF-60",
    }
    assert service._resolve_reference_number(istrv_row) == "ISTRV-REF-60"


def test_transfer_record_properties():
    """Verify TransferRecord model properties expose istv_number, istv_no, and invoice_no from relation."""
    tr = TransferRecord(
        id=uuid4(),
        istv_transaction_id=uuid4(),
        status="IN_TRANSIT",
    )
    # When istv_transaction relation is None
    assert tr.istv_number is None
    assert tr.istv_no is None
    assert tr.invoice_no is None

    # When attached
    mock_tx = MagicMock()
    mock_tx.transaction_number = "ISTV-202611-0099"
    mock_tx.istv_no = "ISTV-REF-99"
    mock_tx.invoice_no = "WB-INV-99"
    tr.istv_transaction = mock_tx

    assert tr.istv_number == "ISTV-202611-0099"
    assert tr.istv_no == "ISTV-REF-99"
    assert tr.invoice_no == "WB-INV-99"
