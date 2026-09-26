# backend/app/repositories/transaction.py
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import AuditLog
from app.models.inventory import InventoryBalance
from app.models.transaction import (
    StockMovement,
    Transaction,
    TransactionLine,
    TransferLine,
    TransferRecord,
)


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lock_inventory_balances_for_update(
        self,
        warehouse_id: uuid.UUID,
        item_ids: List[uuid.UUID],
    ) -> Dict[uuid.UUID, InventoryBalance]:
        """
        Acquires deterministic row locks on inventory balances for the given warehouse and item IDs.
        Items are deterministically ordered by warehouse_id, item_id to eliminate deadlocks (ADR-001, ADR-002).
        """
        if not item_ids:
            return {}

        sorted_item_ids = sorted(item_ids)
        stmt = (
            select(InventoryBalance)
            .where(
                InventoryBalance.warehouse_id == warehouse_id,
                InventoryBalance.item_id.in_(sorted_item_ids),
            )
            .order_by(InventoryBalance.warehouse_id, InventoryBalance.item_id)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        balances = result.scalars().all()
        return {b.item_id: b for b in balances}

    async def get_or_create_balance(
        self,
        warehouse_id: uuid.UUID,
        item_id: uuid.UUID,
        existing_balances: Optional[Dict[uuid.UUID, InventoryBalance]] = None,
    ) -> InventoryBalance:
        """
        Returns existing locked balance or initializes a new one.
        """
        if existing_balances and item_id in existing_balances:
            return existing_balances[item_id]

        stmt = (
            select(InventoryBalance)
            .where(
                InventoryBalance.warehouse_id == warehouse_id,
                InventoryBalance.item_id == item_id,
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        balance = result.scalar_one_or_none()

        if balance is None:
            balance = InventoryBalance(
                id=uuid.uuid4(),
                warehouse_id=warehouse_id,
                item_id=item_id,
                quantity_on_hand=Decimal("0.0000"),
                quantity_reserved=Decimal("0.0000"),
                updated_at=datetime.now(timezone.utc),
            )
            self.session.add(balance)

        return balance

    async def create_transaction(self, transaction: Transaction) -> Transaction:
        """Adds a transaction header to the current session."""
        self.session.add(transaction)
        return transaction

    async def create_transaction_lines(
        self, lines: List[TransactionLine]
    ) -> List[TransactionLine]:
        """Adds transaction lines to the current session."""
        self.session.add_all(lines)
        return lines

    async def create_stock_movement(
        self,
        transaction_id: uuid.UUID,
        transaction_line_id: uuid.UUID,
        item_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        project_id: Optional[uuid.UUID],
        movement_type: str,
        quantity: Decimal,
        running_balance: Optional[Decimal],
        movement_date: date,
    ) -> StockMovement:
        """
        Appends an immutable stock ledger row (ADR-003, ADR-004).
        Enforces movement sign consistency:
        movement_type == 'IN' -> signed_quantity = +quantity (> 0)
        movement_type == 'OUT' -> signed_quantity = -quantity (< 0)
        """
        abs_qty = abs(quantity)
        signed_qty = abs_qty if movement_type == "IN" else -abs_qty

        movement = StockMovement(
            id=uuid.uuid4(),
            transaction_id=transaction_id,
            transaction_line_id=transaction_line_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            project_id=project_id,
            movement_type=movement_type,
            quantity=abs_qty,
            signed_quantity=signed_qty,
            running_balance=running_balance,
            movement_date=movement_date,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(movement)
        return movement

    async def create_audit_log(
        self,
        actor_user_id: Optional[uuid.UUID],
        action: str,
        entity_type: str,
        entity_id: str,
        before_state: Optional[dict] = None,
        after_state: Optional[dict] = None,
        change_summary: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> AuditLog:
        """Records an audit event in audit_logs."""
        audit_log = AuditLog(
            id=uuid.uuid4(),
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            change_summary=change_summary,
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(audit_log)
        return audit_log

    async def get_transaction_by_id(
        self, transaction_id: uuid.UUID
    ) -> Optional[Transaction]:
        """Loads a transaction and eagerly loads its lines."""
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.lines))
            .where(Transaction.id == transaction_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_transfer_record(
        self, transfer_record: TransferRecord
    ) -> TransferRecord:
        """Adds a transfer record to the current session."""
        self.session.add(transfer_record)
        return transfer_record

    async def create_transfer_lines(
        self, lines: List[TransferLine]
    ) -> List[TransferLine]:
        """Adds transfer lines to the current session."""
        self.session.add_all(lines)
        return lines

    async def get_transfer_record_by_istv_id(
        self, istv_id: uuid.UUID
    ) -> Optional[TransferRecord]:
        """Loads a transfer record by its originating ISTV transaction ID."""
        stmt = (
            select(TransferRecord)
            .options(selectinload(TransferRecord.lines))
            .where(TransferRecord.istv_transaction_id == istv_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_transfer_record_by_id(
        self, record_id: uuid.UUID
    ) -> Optional[TransferRecord]:
        """Loads a transfer record by its primary key ID."""
        stmt = (
            select(TransferRecord)
            .options(selectinload(TransferRecord.lines))
            .where(TransferRecord.id == record_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_transactions(
        self,
        transaction_type: Optional[str] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Transaction]:
        """Queries transactions with optional filters, eagerly loading lines ordered by created_at desc."""
        stmt = select(Transaction).options(selectinload(Transaction.lines))

        if transaction_type:
            stmt = stmt.where(Transaction.transaction_type == transaction_type.upper())
        if warehouse_id:
            stmt = stmt.where(
                (Transaction.warehouse_id == warehouse_id)
                | (Transaction.source_warehouse_id == warehouse_id)
                | (Transaction.destination_warehouse_id == warehouse_id)
            )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                (Transaction.transaction_number.ilike(pattern))
                | (Transaction.supplier_name.ilike(pattern))
                | (Transaction.invoice_no.ilike(pattern))
                | (Transaction.siv_no.ilike(pattern))
                | (Transaction.istv_no.ilike(pattern))
                | (Transaction.plate_no.ilike(pattern))
                | (Transaction.driver_name.ilike(pattern))
                | (Transaction.remarks.ilike(pattern))
            )

        stmt = stmt.order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

