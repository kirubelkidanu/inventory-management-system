# backend/app/services/transaction.py
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import (
    Transaction,
    TransactionLine,
    TransferLine,
    TransferRecord,
)
from app.repositories.transaction import TransactionRepository
from app.schemas.transaction import (
    AdjustmentCreate,
    GRVCreate,
    ISTRVCreate,
    ISTVCreate,
    SIVCreate,
    SRVCreate,
)


def _to_uuid(val: Any) -> uuid.UUID:
    """Converts string or UUID into a valid UUID object."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


def generate_transaction_number(prefix: str, tx_date: date) -> str:
    """
    Generates a unique, non-colliding transaction number.
    Format: {PREFIX}-{YYYYMMDD}-{8-hex-chars}
    """
    date_str = tx_date.strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{date_str}-{suffix}"


class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TransactionRepository(session)

    async def create_and_post_grv(
        self,
        user_id: Any,
        payload: GRVCreate,
    ) -> Transaction:
        """
        Atomically creates and posts a Goods Receiving Voucher (GRV).
        Workflow (ADR-001 through ADR-006):
        1. Validates payload lines (non-empty, positive quantities, unique item IDs).
        2. Acquires row locks on inventory_balances for the warehouse and items in deterministic order.
        3. Creates Transaction record with status 'POSTED'.
        4. Creates TransactionLine records.
        5. Updates inventory_balances (increments quantity_on_hand).
        6. Appends immutable StockMovement records (type 'IN', positive signed_quantity, running balance).
        7. Records audit log.
        8. Commits atomically in one PostgreSQL transaction; rolls back on any error.
        """
        # Validate lines
        if not payload.lines:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Transaction must contain at least one line.",
            )

        item_ids = [line.item_id for line in payload.lines]
        if len(item_ids) != len(set(item_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate item in transaction lines is not allowed (ADR-006).",
            )

        for line in payload.lines:
            if line.quantity <= Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Line quantity must be greater than zero. Received: {line.quantity}",
                )

        parsed_user_id = _to_uuid(user_id)
        tx_date = payload.transaction_date or date.today()
        tx_number = generate_transaction_number("GRV", tx_date)
        tx_id = uuid.uuid4()
        now_utc = datetime.now(timezone.utc)

        try:
            # Deterministic balance row locking
            locked_balances = await self.repo.lock_inventory_balances_for_update(
                warehouse_id=payload.warehouse_id,
                item_ids=item_ids,
            )

            # Create Transaction header
            transaction = Transaction(
                id=tx_id,
                transaction_number=tx_number,
                transaction_type="GRV",
                status="POSTED",
                transaction_date=tx_date,
                warehouse_id=payload.warehouse_id,
                project_id=payload.project_id,
                supplier_name=payload.supplier_name,
                invoice_no=payload.invoice_no,
                received_grv_no=payload.received_grv_no,
                store_no=payload.store_no,
                remarks=payload.remarks,
                created_by=parsed_user_id,
                created_at=now_utc,
                posted_by=parsed_user_id,
                posted_at=now_utc,
            )
            # Create Transaction lines
            lines: List[TransactionLine] = []
            for idx, line_input in enumerate(payload.lines, start=1):
                line = TransactionLine(
                    id=uuid.uuid4(),
                    transaction_id=tx_id,
                    line_number=idx,
                    item_id=line_input.item_id,
                    quantity=line_input.quantity,
                    unit=line_input.unit,
                    remarks=line_input.remarks,
                )
                lines.append(line)
            transaction.lines = lines

            await self.repo.create_transaction(transaction)
            await self.repo.create_transaction_lines(lines)
            await self.session.flush()

            # Update balances and append stock movements
            for line in lines:
                balance = await self.repo.get_or_create_balance(
                    warehouse_id=payload.warehouse_id,
                    item_id=line.item_id,
                    existing_balances=locked_balances,
                )
                balance.quantity_on_hand += line.quantity
                balance.updated_at = now_utc
                running_bal = balance.quantity_on_hand

                await self.repo.create_stock_movement(
                    transaction_id=tx_id,
                    transaction_line_id=line.id,
                    item_id=line.item_id,
                    warehouse_id=payload.warehouse_id,
                    project_id=payload.project_id,
                    movement_type="IN",
                    quantity=line.quantity,
                    running_balance=running_bal,
                    movement_date=tx_date,
                )

            # Record audit log
            await self.repo.create_audit_log(
                actor_user_id=parsed_user_id,
                action="POST_GRV",
                entity_type="TRANSACTION",
                entity_id=str(tx_id),
                before_state=None,
                after_state={
                    "transaction_number": tx_number,
                    "transaction_type": "GRV",
                    "status": "POSTED",
                    "warehouse_id": str(payload.warehouse_id),
                    "lines_count": len(lines),
                    "total_quantity": str(sum(l.quantity for l in lines)),
                },
                change_summary=f"Created and posted GRV {tx_number} with {len(lines)} item lines.",
                reason="GRV Receipt",
            )

            await self.session.commit()
            refreshed = await self.repo.get_transaction_by_id(tx_id)
            return refreshed or transaction

        except Exception:
            await self.session.rollback()
            raise

    async def create_and_post_siv(
        self,
        user_id: Any,
        payload: SIVCreate,
    ) -> Transaction:
        """
        Atomically creates and posts a Store Issue Voucher (SIV).
        Workflow (ADR-001 through ADR-006):
        1. Validates payload lines (non-empty, positive quantities, unique item IDs).
        2. Acquires row locks on inventory_balances for the warehouse and items in deterministic order.
        3. Verifies available stock (quantity_on_hand - quantity_reserved >= requested_quantity).
           Rejects with HTTP 400 if stock is insufficient.
        4. Creates Transaction record with status 'POSTED'.
        5. Creates TransactionLine records.
        6. Updates inventory_balances (decrements quantity_on_hand).
        7. Appends immutable StockMovement records (type 'OUT', negative signed_quantity, running balance).
        8. Records audit log.
        9. Commits atomically in one PostgreSQL transaction; rolls back on any error.
        """
        if not payload.lines:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Transaction must contain at least one line.",
            )

        item_ids = [line.item_id for line in payload.lines]
        if len(item_ids) != len(set(item_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate item in transaction lines is not allowed (ADR-006).",
            )

        for line in payload.lines:
            if line.quantity <= Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Line quantity must be greater than zero. Received: {line.quantity}",
                )

        parsed_user_id = _to_uuid(user_id)
        tx_date = payload.transaction_date or date.today()
        tx_number = generate_transaction_number("SIV", tx_date)
        tx_id = uuid.uuid4()
        now_utc = datetime.now(timezone.utc)

        try:
            # Deterministic balance row locking
            locked_balances = await self.repo.lock_inventory_balances_for_update(
                warehouse_id=payload.warehouse_id,
                item_ids=item_ids,
            )

            # Verify available stock for every line BEFORE modifying anything
            for line_input in payload.lines:
                balance = locked_balances.get(line_input.item_id)
                available = (
                    (balance.quantity_on_hand - balance.quantity_reserved)
                    if balance is not None
                    else Decimal("0.0000")
                )
                if available < line_input.quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Insufficient stock for item {line_input.item_id}. "
                            f"Available: {available}, Requested: {line_input.quantity}"
                        ),
                    )

            # Create Transaction header
            transaction = Transaction(
                id=tx_id,
                transaction_number=tx_number,
                transaction_type="SIV",
                status="POSTED",
                transaction_date=tx_date,
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
                created_by=parsed_user_id,
                created_at=now_utc,
                posted_by=parsed_user_id,
                posted_at=now_utc,
            )
            # Create Transaction lines
            lines: List[TransactionLine] = []
            for idx, line_input in enumerate(payload.lines, start=1):
                line = TransactionLine(
                    id=uuid.uuid4(),
                    transaction_id=tx_id,
                    line_number=idx,
                    item_id=line_input.item_id,
                    quantity=line_input.quantity,
                    unit=line_input.unit,
                    remarks=line_input.remarks,
                )
                lines.append(line)
            transaction.lines = lines

            await self.repo.create_transaction(transaction)
            await self.repo.create_transaction_lines(lines)
            await self.session.flush()

            # Decrement balances and append stock movements
            for line in lines:
                balance = locked_balances[line.item_id]
                balance.quantity_on_hand -= line.quantity
                balance.updated_at = now_utc
                running_bal = balance.quantity_on_hand

                await self.repo.create_stock_movement(
                    transaction_id=tx_id,
                    transaction_line_id=line.id,
                    item_id=line.item_id,
                    warehouse_id=payload.warehouse_id,
                    project_id=payload.project_id,
                    movement_type="OUT",
                    quantity=line.quantity,
                    running_balance=running_bal,
                    movement_date=tx_date,
                )

            # Record audit log
            await self.repo.create_audit_log(
                actor_user_id=parsed_user_id,
                action="POST_SIV",
                entity_type="TRANSACTION",
                entity_id=str(tx_id),
                before_state=None,
                after_state={
                    "transaction_number": tx_number,
                    "transaction_type": "SIV",
                    "status": "POSTED",
                    "warehouse_id": str(payload.warehouse_id),
                    "lines_count": len(lines),
                    "total_quantity": str(sum(l.quantity for l in lines)),
                },
                change_summary=f"Created and posted SIV {tx_number} with {len(lines)} item lines.",
                reason="SIV Issue",
            )

            await self.session.commit()
            refreshed = await self.repo.get_transaction_by_id(tx_id)
            return refreshed or transaction

        except Exception:
            await self.session.rollback()
            raise

    async def create_and_post_istv(
        self,
        user_id: Any,
        payload: ISTVCreate,
    ) -> Transaction:
        """
        Atomically creates and posts an Inter-Store Transfer Voucher (ISTV).
        Workflow (ADR-001, ADR-002, ADR-003, ADR-004):
        1. Validates that source and destination warehouses are different.
        2. Validates lines (non-empty, positive quantities, unique item IDs).
        3. Acquires deterministic row locks on source warehouse inventory_balances.
        4. Verifies available stock on source warehouse (quantity_on_hand - quantity_reserved >= quantity).
        5. Creates Transaction record with status 'POSTED' (source_warehouse_id and destination_warehouse_id populated).
        6. Creates TransactionLine records.
        7. Decrements source inventory_balances (quantity_on_hand -= quantity).
        8. Inserts immutable StockMovement records (movement_type='OUT', signed_quantity = -quantity).
        9. Creates TransferRecord (status='IN_TRANSIT') and TransferLines (sent_quantity=quantity, received_quantity=0).
        10. Destination warehouse balance remains UNTOUCHED.
        11. Records audit log.
        12. Commits atomically in one PostgreSQL transaction; rolls back on any error.
        """
        if payload.source_warehouse_id == payload.destination_warehouse_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source warehouse and destination warehouse must be different.",
            )

        if not payload.lines:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Transaction must contain at least one line.",
            )

        item_ids = [line.item_id for line in payload.lines]
        if len(item_ids) != len(set(item_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate item in transaction lines is not allowed (ADR-006).",
            )

        for line in payload.lines:
            if line.quantity <= Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Line quantity must be greater than zero. Received: {line.quantity}",
                )

        parsed_user_id = _to_uuid(user_id)
        tx_date = payload.transaction_date or date.today()
        tx_number = generate_transaction_number("ISTV", tx_date)
        tx_id = uuid.uuid4()
        now_utc = datetime.now(timezone.utc)

        try:
            # Deterministic balance row locking on source warehouse
            locked_balances = await self.repo.lock_inventory_balances_for_update(
                warehouse_id=payload.source_warehouse_id,
                item_ids=item_ids,
            )

            # Verify available stock for every line BEFORE modifying anything
            for line_input in payload.lines:
                balance = locked_balances.get(line_input.item_id)
                available = (
                    (balance.quantity_on_hand - balance.quantity_reserved)
                    if balance is not None
                    else Decimal("0.0000")
                )
                if available < line_input.quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Insufficient stock for item {line_input.item_id} at source warehouse. "
                            f"Available: {available}, Requested: {line_input.quantity}"
                        ),
                    )

            # Create Transaction header
            transaction = Transaction(
                id=tx_id,
                transaction_number=tx_number,
                transaction_type="ISTV",
                status="POSTED",
                transaction_date=tx_date,
                source_warehouse_id=payload.source_warehouse_id,
                destination_warehouse_id=payload.destination_warehouse_id,
                warehouse_id=payload.source_warehouse_id,
                project_id=payload.project_id,
                istv_no=payload.istv_no,
                plate_no=payload.plate_no,
                driver_name=payload.driver_name,
                material_summary=payload.material_summary,
                remarks=payload.remarks,
                created_by=parsed_user_id,
                created_at=now_utc,
                posted_by=parsed_user_id,
                posted_at=now_utc,
            )
            # Create Transaction lines
            lines: List[TransactionLine] = []
            for idx, line_input in enumerate(payload.lines, start=1):
                line = TransactionLine(
                    id=uuid.uuid4(),
                    transaction_id=tx_id,
                    line_number=idx,
                    item_id=line_input.item_id,
                    quantity=line_input.quantity,
                    unit=line_input.unit,
                    remarks=line_input.remarks,
                )
                lines.append(line)
            transaction.lines = lines

            await self.repo.create_transaction(transaction)
            await self.repo.create_transaction_lines(lines)
            await self.session.flush()

            # Decrement source balances and append stock movements
            for line in lines:
                balance = locked_balances[line.item_id]
                balance.quantity_on_hand -= line.quantity
                balance.updated_at = now_utc
                running_bal = balance.quantity_on_hand

                await self.repo.create_stock_movement(
                    transaction_id=tx_id,
                    transaction_line_id=line.id,
                    item_id=line.item_id,
                    warehouse_id=payload.source_warehouse_id,
                    project_id=payload.project_id,
                    movement_type="OUT",
                    quantity=line.quantity,
                    running_balance=running_bal,
                    movement_date=tx_date,
                )

            # Create TransferRecord and TransferLine records
            transfer_record = TransferRecord(
                id=uuid.uuid4(),
                istv_transaction_id=tx_id,
                source_warehouse_id=payload.source_warehouse_id,
                destination_warehouse_id=payload.destination_warehouse_id,
                plate_no=payload.plate_no,
                driver_name=payload.driver_name,
                status="IN_TRANSIT",
                created_at=now_utc,
            )
            await self.repo.create_transfer_record(transfer_record)

            transfer_lines: List[TransferLine] = []
            for line in lines:
                t_line = TransferLine(
                    id=uuid.uuid4(),
                    transfer_record_id=transfer_record.id,
                    item_id=line.item_id,
                    sent_quantity=line.quantity,
                    received_quantity=Decimal("0.0000"),
                )
                transfer_lines.append(t_line)
            await self.repo.create_transfer_lines(transfer_lines)
            transfer_record.lines = transfer_lines

            # Record audit log
            await self.repo.create_audit_log(
                actor_user_id=parsed_user_id,
                action="POST_ISTV",
                entity_type="TRANSACTION",
                entity_id=str(tx_id),
                before_state=None,
                after_state={
                    "transaction_number": tx_number,
                    "transaction_type": "ISTV",
                    "status": "POSTED",
                    "source_warehouse_id": str(payload.source_warehouse_id),
                    "destination_warehouse_id": str(payload.destination_warehouse_id),
                    "lines_count": len(lines),
                    "total_quantity": str(sum(l.quantity for l in lines)),
                    "transfer_record_id": str(transfer_record.id),
                },
                change_summary=f"Created and posted ISTV {tx_number} with {len(lines)} item lines dispatched in transit.",
                reason="Inter-Store Transfer Dispatch",
            )

            await self.session.commit()
            refreshed = await self.repo.get_transaction_by_id(tx_id)
            return refreshed or transaction

        except Exception:
            await self.session.rollback()
            raise

    async def create_and_post_istrv(
        self,
        user_id: Any,
        payload: ISTRVCreate,
    ) -> Transaction:
        """
        Atomically creates and posts an Inter-Store Transfer Receiving Voucher (ISTRV).
        Workflow (ADR-001, ADR-002, ADR-003, ADR-004, ADR-005):
        1. Fetches TransferRecord by istv_transaction_id. Raises HTTP 404 if not found.
        2. Validates transfer status (rejects COMPLETED or CANCELLED with HTTP 400).
        3. Validates destination warehouse matches transfer_record.destination_warehouse_id.
        4. Validates lines (non-empty, positive quantities, unique item IDs).
        5. For each receiving line, verifies item is part of transfer and receiving quantity
           <= remaining_quantity (sent_quantity - received_quantity).
           Rejects over-receiving with HTTP 400 (ADR-005).
        6. Acquires deterministic row locks on destination warehouse inventory_balances.
        7. Creates Transaction record with status 'POSTED' (reference_transaction_id=istv_transaction_id).
        8. Creates TransactionLine records.
        9. Increments destination inventory_balances (quantity_on_hand += quantity).
        10. Inserts immutable StockMovement records (movement_type='IN', signed_quantity = +quantity).
        11. Updates TransferLine received_quantity += quantity.
        12. Updates TransferRecord status: 'COMPLETED' (with completed_at) if all items fully received,
            otherwise 'PARTIALLY_RECEIVED'.
        13. Records audit log.
        14. Commits atomically in one PostgreSQL transaction; rolls back on any error.
        """
        if not payload.lines:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Transaction must contain at least one line.",
            )

        item_ids = [line.item_id for line in payload.lines]
        if len(item_ids) != len(set(item_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate item in transaction lines is not allowed (ADR-006).",
            )

        for line in payload.lines:
            if line.quantity <= Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Line quantity must be greater than zero. Received: {line.quantity}",
                )

        parsed_user_id = _to_uuid(user_id)
        tx_date = payload.transaction_date or date.today()
        tx_number = generate_transaction_number("ISTRV", tx_date)
        tx_id = uuid.uuid4()
        now_utc = datetime.now(timezone.utc)

        try:
            # 1. Fetch TransferRecord
            transfer_record = await self.repo.get_transfer_record_by_istv_id(payload.istv_transaction_id)
            if transfer_record is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Transfer record for ISTV {payload.istv_transaction_id} not found.",
                )

            # 2. Check transfer lifecycle state
            if transfer_record.status == "COMPLETED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Transfer record for ISTV {payload.istv_transaction_id} is already COMPLETED.",
                )
            if transfer_record.status == "CANCELLED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Transfer record for ISTV {payload.istv_transaction_id} is CANCELLED.",
                )

            # 3. Verify destination warehouse match
            if payload.destination_warehouse_id != transfer_record.destination_warehouse_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Destination warehouse {payload.destination_warehouse_id} does not match "
                        f"transfer destination warehouse {transfer_record.destination_warehouse_id}."
                    ),
                )

            # 4. Verify in-transit lines and remaining quantities (ADR-005: Over-receiving must never be allowed)
            transfer_lines_by_item = {tl.item_id: tl for tl in transfer_record.lines}
            for line_input in payload.lines:
                tl = transfer_lines_by_item.get(line_input.item_id)
                if tl is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Item {line_input.item_id} is not part of transfer record {transfer_record.id}.",
                    )
                remaining = tl.sent_quantity - tl.received_quantity
                if line_input.quantity > remaining:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Cannot receive {line_input.quantity} for item {line_input.item_id}. "
                            f"Remaining in-transit quantity is {remaining}. Over-receiving is prohibited (ADR-005)."
                        ),
                    )

            # 5. Look up units from originating ISTV transaction lines
            istv_tx = await self.repo.get_transaction_by_id(payload.istv_transaction_id)
            unit_by_item: dict[uuid.UUID, str] = {}
            if istv_tx and istv_tx.lines:
                unit_by_item = {l.item_id: l.unit for l in istv_tx.lines}

            # 6. Deterministic balance row locking on destination warehouse
            locked_balances = await self.repo.lock_inventory_balances_for_update(
                warehouse_id=payload.destination_warehouse_id,
                item_ids=item_ids,
            )

            # 7. Create Transaction header
            transaction = Transaction(
                id=tx_id,
                transaction_number=tx_number,
                transaction_type="ISTRV",
                status="POSTED",
                transaction_date=tx_date,
                destination_warehouse_id=payload.destination_warehouse_id,
                warehouse_id=payload.destination_warehouse_id,
                reference_transaction_id=payload.istv_transaction_id,
                remarks=payload.remarks,
                created_by=parsed_user_id,
                created_at=now_utc,
                posted_by=parsed_user_id,
                posted_at=now_utc,
            )
            # 8. Create Transaction lines
            lines: List[TransactionLine] = []
            for idx, line_input in enumerate(payload.lines, start=1):
                unit = unit_by_item.get(line_input.item_id, "PCS")
                line = TransactionLine(
                    id=uuid.uuid4(),
                    transaction_id=tx_id,
                    line_number=idx,
                    item_id=line_input.item_id,
                    quantity=line_input.quantity,
                    unit=unit,
                    remarks=line_input.remarks,
                )
                lines.append(line)
            transaction.lines = lines

            await self.repo.create_transaction(transaction)
            await self.repo.create_transaction_lines(lines)
            await self.session.flush()

            # 9. Increment destination warehouse balances, insert IN movements, update transfer lines
            for line in lines:
                balance = await self.repo.get_or_create_balance(
                    warehouse_id=payload.destination_warehouse_id,
                    item_id=line.item_id,
                    existing_balances=locked_balances,
                )
                balance.quantity_on_hand += line.quantity
                balance.updated_at = now_utc
                running_bal = balance.quantity_on_hand

                await self.repo.create_stock_movement(
                    transaction_id=tx_id,
                    transaction_line_id=line.id,
                    item_id=line.item_id,
                    warehouse_id=payload.destination_warehouse_id,
                    project_id=None,
                    movement_type="IN",
                    quantity=line.quantity,
                    running_balance=running_bal,
                    movement_date=tx_date,
                )

                # Update cumulative received quantity on transfer line
                tl = transfer_lines_by_item[line.item_id]
                tl.received_quantity += line.quantity

            # 10. Update TransferRecord status
            all_completed = all(
                tl.received_quantity >= tl.sent_quantity
                for tl in transfer_record.lines
            )
            if all_completed:
                transfer_record.status = "COMPLETED"
                transfer_record.completed_at = now_utc
            else:
                transfer_record.status = "PARTIALLY_RECEIVED"

            # 11. Record audit log
            await self.repo.create_audit_log(
                actor_user_id=parsed_user_id,
                action="POST_ISTRV",
                entity_type="TRANSACTION",
                entity_id=str(tx_id),
                before_state=None,
                after_state={
                    "transaction_number": tx_number,
                    "transaction_type": "ISTRV",
                    "status": "POSTED",
                    "istv_transaction_id": str(payload.istv_transaction_id),
                    "destination_warehouse_id": str(payload.destination_warehouse_id),
                    "lines_count": len(lines),
                    "total_quantity": str(sum(l.quantity for l in lines)),
                    "transfer_status": transfer_record.status,
                },
                change_summary=(
                    f"Created and posted ISTRV {tx_number} with {len(lines)} item lines received. "
                    f"Transfer record status updated to {transfer_record.status}."
                ),
                reason="Inter-Store Transfer Receipt",
            )

            await self.session.commit()
            refreshed = await self.repo.get_transaction_by_id(tx_id)
            return refreshed or transaction

        except Exception:
            await self.session.rollback()
            raise

    async def get_transfer_record_by_istv_id(
        self,
        istv_id: uuid.UUID,
    ) -> Optional[TransferRecord]:
        return await self.repo.get_transfer_record_by_istv_id(istv_id)

    async def create_and_post_srv(
        self,
        user_id: Any,
        payload: SRVCreate,
    ) -> Transaction:
        """
        Atomically creates and posts a Store Return Voucher (SRV).
        Workflow (ADR-001 through ADR-006):
        1. Validates payload lines (non-empty, positive quantities, unique item IDs).
        2. Retrieves and validates referenced SIV transaction:
           - Must exist (404 if not found).
           - Must be transaction_type == "SIV" (400 if not).
           - Must be status == "POSTED" (400 if not).
        3. Verifies all returned item IDs were part of the referenced SIV line items (400 if not).
        4. Acquires row locks on inventory_balances for warehouse and items in deterministic order.
        5. Creates Transaction record with status 'POSTED' and reference_transaction_id=payload.reference_siv_id.
        6. Creates TransactionLine records.
        7. Updates inventory_balances (increments quantity_on_hand).
        8. Appends immutable StockMovement records (type 'IN', positive signed_quantity, running balance).
        9. Records audit log.
        10. Commits atomically in one PostgreSQL transaction; rolls back on any error.
        """
        if not payload.lines:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Transaction must contain at least one line.",
            )

        item_ids = [line.item_id for line in payload.lines]
        if len(item_ids) != len(set(item_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate item in transaction lines is not allowed (ADR-006).",
            )

        for line in payload.lines:
            if line.quantity <= Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Line quantity must be greater than zero. Received: {line.quantity}",
                )

        parsed_user_id = _to_uuid(user_id)
        tx_date = payload.transaction_date or date.today()
        tx_number = generate_transaction_number("SRV", tx_date)
        tx_id = uuid.uuid4()
        now_utc = datetime.now(timezone.utc)

        try:
            # 1. Fetch referenced transaction
            ref_tx = await self.repo.get_transaction_by_id(payload.reference_siv_id)
            if ref_tx is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Referenced SIV {payload.reference_siv_id} not found.",
                )
            if ref_tx.transaction_type != "SIV":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Referenced transaction {payload.reference_siv_id} is not an SIV (found {ref_tx.transaction_type}).",
                )
            if ref_tx.status != "POSTED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Referenced SIV {payload.reference_siv_id} is not POSTED (status is {ref_tx.status}).",
                )

            # 2. Verify all returned item IDs exist on referenced SIV
            siv_item_ids = {line.item_id for line in (ref_tx.lines or [])}
            for line in payload.lines:
                if line.item_id not in siv_item_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Item {line.item_id} was not issued on referenced SIV {payload.reference_siv_id}.",
                    )

            # 3. Deterministic balance row locking
            locked_balances = await self.repo.lock_inventory_balances_for_update(
                warehouse_id=payload.warehouse_id,
                item_ids=item_ids,
            )

            # 4. Create Transaction header
            transaction = Transaction(
                id=tx_id,
                transaction_number=tx_number,
                transaction_type="SRV",
                status="POSTED",
                transaction_date=tx_date,
                warehouse_id=payload.warehouse_id,
                project_id=payload.project_id or ref_tx.project_id,
                reference_transaction_id=payload.reference_siv_id,
                remarks=payload.remarks,
                created_by=parsed_user_id,
                created_at=now_utc,
                posted_by=parsed_user_id,
                posted_at=now_utc,
            )
            # 5. Create Transaction lines
            lines: List[TransactionLine] = []
            for idx, line_input in enumerate(payload.lines, start=1):
                line = TransactionLine(
                    id=uuid.uuid4(),
                    transaction_id=tx_id,
                    line_number=idx,
                    item_id=line_input.item_id,
                    quantity=line_input.quantity,
                    unit=line_input.unit,
                    remarks=line_input.remarks,
                )
                lines.append(line)
            transaction.lines = lines

            await self.repo.create_transaction(transaction)
            await self.repo.create_transaction_lines(lines)
            await self.session.flush()

            # 6. Update balances and append stock movements (IN)
            for line in lines:
                balance = await self.repo.get_or_create_balance(
                    warehouse_id=payload.warehouse_id,
                    item_id=line.item_id,
                    existing_balances=locked_balances,
                )
                balance.quantity_on_hand += line.quantity
                balance.updated_at = now_utc
                running_bal = balance.quantity_on_hand

                await self.repo.create_stock_movement(
                    transaction_id=tx_id,
                    transaction_line_id=line.id,
                    item_id=line.item_id,
                    warehouse_id=payload.warehouse_id,
                    project_id=payload.project_id or ref_tx.project_id,
                    movement_type="IN",
                    quantity=line.quantity,
                    running_balance=running_bal,
                    movement_date=tx_date,
                )

            # 7. Record audit log
            await self.repo.create_audit_log(
                actor_user_id=parsed_user_id,
                action="POST_SRV",
                entity_type="TRANSACTION",
                entity_id=str(tx_id),
                before_state=None,
                after_state={
                    "transaction_number": tx_number,
                    "transaction_type": "SRV",
                    "status": "POSTED",
                    "warehouse_id": str(payload.warehouse_id),
                    "reference_siv_id": str(payload.reference_siv_id),
                    "lines_count": len(lines),
                    "total_quantity": str(sum(l.quantity for l in lines)),
                },
                change_summary=f"Created and posted SRV {tx_number} returning stock against SIV {payload.reference_siv_id}.",
                reason="Store Return Voucher",
            )

            await self.session.commit()
            refreshed = await self.repo.get_transaction_by_id(tx_id)
            return refreshed or transaction

        except Exception:
            await self.session.rollback()
            raise

    async def create_and_post_adjustment(
        self,
        user_id: Any,
        payload: AdjustmentCreate,
    ) -> Transaction:
        """
        Atomically creates and posts a Stock Adjustment (ADJUSTMENT).
        Workflow (ADR-001 through ADR-006):
        1. Validates payload lines (non-empty, positive quantities, unique item IDs, valid direction).
        2. Validates non-empty adjustment_reason.
        3. Acquires row locks on inventory_balances in deterministic order.
        4. For downward adjustments (direction == 'OUT'):
           - Verifies available stock (quantity_on_hand - quantity_reserved >= line.quantity).
           - Rejects with HTTP 400 if stock is insufficient to prevent negative inventory.
        5. Creates Transaction record with status 'POSTED', adjustment_reason=payload.adjustment_reason.
        6. Creates TransactionLine records.
        7. For each line:
           - If direction == 'IN': increments balance, appends 'IN' movement (+quantity).
           - If direction == 'OUT': decrements balance, appends 'OUT' movement (-signed_quantity).
        8. Records audit log with before/after state snapshots.
        9. Commits atomically in one PostgreSQL transaction; rolls back on any error.
        """
        if not payload.lines:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Transaction must contain at least one line.",
            )

        if not payload.adjustment_reason or not payload.adjustment_reason.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Adjustment reason cannot be empty or whitespace.",
            )

        item_ids = [line.item_id for line in payload.lines]
        if len(item_ids) != len(set(item_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate item in transaction lines is not allowed (ADR-006).",
            )

        for line in payload.lines:
            if line.quantity <= Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Line quantity must be greater than zero. Received: {line.quantity}",
                )
            if line.direction not in ("IN", "OUT"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Line direction must be 'IN' or 'OUT'. Received: {line.direction}",
                )

        parsed_user_id = _to_uuid(user_id)
        tx_date = payload.transaction_date or date.today()
        tx_number = generate_transaction_number("ADJ", tx_date)
        tx_id = uuid.uuid4()
        now_utc = datetime.now(timezone.utc)

        try:
            # 1. Deterministic balance row locking
            locked_balances = await self.repo.lock_inventory_balances_for_update(
                warehouse_id=payload.warehouse_id,
                item_ids=item_ids,
            )

            # 2. Verify available stock for downward adjustment lines
            for line_input in payload.lines:
                if line_input.direction == "OUT":
                    balance = locked_balances.get(line_input.item_id)
                    available = (
                        (balance.quantity_on_hand - balance.quantity_reserved)
                        if balance is not None
                        else Decimal("0.0000")
                    )
                    if available < line_input.quantity:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Insufficient stock for downward adjustment of item {line_input.item_id}. "
                                f"Available: {available}, Requested reduction: {line_input.quantity}"
                            ),
                        )

            # 3. Capture snapshot before modification for audit log
            before_snapshot = {
                str(item_id): str(bal.quantity_on_hand)
                for item_id, bal in locked_balances.items()
            }

            # 4. Create Transaction header
            transaction = Transaction(
                id=tx_id,
                transaction_number=tx_number,
                transaction_type="ADJUSTMENT",
                status="POSTED",
                transaction_date=tx_date,
                warehouse_id=payload.warehouse_id,
                project_id=payload.project_id,
                adjustment_reason=payload.adjustment_reason.strip(),
                remarks=payload.remarks,
                created_by=parsed_user_id,
                created_at=now_utc,
                posted_by=parsed_user_id,
                posted_at=now_utc,
            )
            # 5. Create Transaction lines
            lines: List[TransactionLine] = []
            for idx, line_input in enumerate(payload.lines, start=1):
                line = TransactionLine(
                    id=uuid.uuid4(),
                    transaction_id=tx_id,
                    line_number=idx,
                    item_id=line_input.item_id,
                    quantity=line_input.quantity,
                    unit=line_input.unit,
                    remarks=line_input.remarks,
                )
                lines.append(line)
            transaction.lines = lines

            await self.repo.create_transaction(transaction)
            await self.repo.create_transaction_lines(lines)
            await self.session.flush()

            # 6. Update balances and append stock movements
            for idx, line in enumerate(lines):
                line_input = payload.lines[idx]
                balance = await self.repo.get_or_create_balance(
                    warehouse_id=payload.warehouse_id,
                    item_id=line.item_id,
                    existing_balances=locked_balances,
                )

                if line_input.direction == "IN":
                    balance.quantity_on_hand += line.quantity
                    movement_type = "IN"
                else:
                    balance.quantity_on_hand -= line.quantity
                    movement_type = "OUT"

                balance.updated_at = now_utc
                running_bal = balance.quantity_on_hand

                await self.repo.create_stock_movement(
                    transaction_id=tx_id,
                    transaction_line_id=line.id,
                    item_id=line.item_id,
                    warehouse_id=payload.warehouse_id,
                    project_id=payload.project_id,
                    movement_type=movement_type,
                    quantity=line.quantity,
                    running_balance=running_bal,
                    movement_date=tx_date,
                )

            # 7. Record audit log
            await self.repo.create_audit_log(
                actor_user_id=parsed_user_id,
                action="POST_ADJUSTMENT",
                entity_type="TRANSACTION",
                entity_id=str(tx_id),
                before_state=before_snapshot,
                after_state={
                    "transaction_number": tx_number,
                    "transaction_type": "ADJUSTMENT",
                    "status": "POSTED",
                    "warehouse_id": str(payload.warehouse_id),
                    "adjustment_reason": payload.adjustment_reason.strip(),
                    "lines_count": len(lines),
                    "lines": [
                        {
                            "item_id": str(l.item_id),
                            "direction": l.direction,
                            "quantity": str(l.quantity),
                        }
                        for l in payload.lines
                    ],
                },
                change_summary=f"Created and posted Adjustment {tx_number} with reason: {payload.adjustment_reason.strip()}",
                reason=payload.adjustment_reason.strip(),
            )

            await self.session.commit()
            refreshed = await self.repo.get_transaction_by_id(tx_id)
            return refreshed or transaction

        except Exception:
            await self.session.rollback()
            raise

    async def list_transactions(
        self,
        transaction_type: Optional[str] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Transaction]:
        """Lists transactions with optional filters and eager-loaded lines."""
        return await self.repo.list_transactions(
            transaction_type=transaction_type,
            warehouse_id=warehouse_id,
            search=search,
            skip=skip,
            limit=limit,
        )

