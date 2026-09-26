# backend/app/services/reconciliation.py
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.inventory import InventoryBalance
from app.models.item import Item
from app.models.warehouse import Warehouse
from app.repositories.transaction import TransactionRepository
from app.schemas.reconciliation import (
    CountSheetItem,
    CountSheetResponse,
    PhysicalCountSubmitRequest,
    ReconciliationCommitRequest,
    ReconciliationPreviewResponse,
    VarianceItem,
)
from app.schemas.transaction import AdjustmentCreate, AdjustmentLineCreate
from app.services.transaction import TransactionService


def _to_uuid(val: Any) -> uuid.UUID:
    """Converts string or UUID into a valid UUID object."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


class ReconciliationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tx_service = TransactionService(session)
        self.tx_repo = TransactionRepository(session)

    async def generate_count_sheet(
        self, warehouse_id: uuid.UUID
    ) -> CountSheetResponse:
        """
        Generates a physical audit count sheet template for a warehouse,
        listing all active items in the catalog and their current system quantity on hand.
        """
        stmt_wh = select(Warehouse).where(Warehouse.id == warehouse_id)
        res_wh = await self.session.execute(stmt_wh)
        wh = res_wh.scalar_one_or_none()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Warehouse {warehouse_id} not found.",
            )

        stmt = (
            select(
                Item.id.label("item_id"),
                Item.item_code,
                Item.description.label("item_description"),
                Category.name.label("category_name"),
                Item.default_unit.label("unit"),
                func.coalesce(InventoryBalance.quantity_on_hand, Decimal("0.0000")).label(
                    "system_quantity_on_hand"
                ),
            )
            .join(Category, Item.category_id == Category.id)
            .outerjoin(
                InventoryBalance,
                (InventoryBalance.item_id == Item.id)
                & (InventoryBalance.warehouse_id == warehouse_id),
            )
            .where(Item.is_active == True)
            .order_by(Category.code, Item.item_code)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        sheet_items = [
            CountSheetItem(
                item_id=r.item_id,
                item_code=r.item_code,
                item_description=r.item_description,
                category_name=r.category_name,
                unit=r.unit,
                system_quantity_on_hand=r.system_quantity_on_hand,
            )
            for r in rows
        ]

        return CountSheetResponse(
            warehouse_id=wh.id,
            warehouse_code=wh.code,
            warehouse_name=wh.name,
            generated_at=datetime.now(timezone.utc),
            total_items=len(sheet_items),
            items=sheet_items,
        )

    async def calculate_variance_preview(
        self, payload: PhysicalCountSubmitRequest
    ) -> ReconciliationPreviewResponse:
        """
        Calculates and classifies physical count variances against current system balances.
        Surplus: counted > system -> direction 'IN'
        Deficit: counted < system -> direction 'OUT'
        Match: counted == system -> direction 'NONE'
        """
        stmt_wh = select(Warehouse).where(Warehouse.id == payload.warehouse_id)
        res_wh = await self.session.execute(stmt_wh)
        wh = res_wh.scalar_one_or_none()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Warehouse {payload.warehouse_id} not found.",
            )

        item_ids = [c.item_id for c in payload.counts]

        # Fetch items
        stmt_items = select(Item).where(Item.id.in_(item_ids))
        res_items = await self.session.execute(stmt_items)
        items_map = {i.id: i for i in res_items.scalars().all()}

        missing = [i_id for i_id in item_ids if i_id not in items_map]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item {missing[0]} not found in catalog.",
            )

        # Fetch current inventory balances
        stmt_bal = select(InventoryBalance).where(
            InventoryBalance.warehouse_id == payload.warehouse_id,
            InventoryBalance.item_id.in_(item_ids),
        )
        res_bal = await self.session.execute(stmt_bal)
        balances_map = {b.item_id: b.quantity_on_hand for b in res_bal.scalars().all()}

        variances: List[VarianceItem] = []
        matched_count = 0
        surplus_count = 0
        deficit_count = 0

        for c in payload.counts:
            item = items_map[c.item_id]
            system_qty = balances_map.get(c.item_id, Decimal("0.0000"))
            counted_qty = c.counted_quantity
            raw_diff = counted_qty - system_qty

            if raw_diff > Decimal("0"):
                direction = "IN"
                var_qty = raw_diff
                surplus_count += 1
            elif raw_diff < Decimal("0"):
                direction = "OUT"
                var_qty = abs(raw_diff)
                deficit_count += 1
            else:
                direction = "NONE"
                var_qty = Decimal("0.0000")
                matched_count += 1

            variances.append(
                VarianceItem(
                    item_id=c.item_id,
                    item_code=item.item_code,
                    item_description=item.description,
                    unit=item.default_unit,
                    system_quantity=system_qty,
                    counted_quantity=counted_qty,
                    variance_quantity=var_qty,
                    adjustment_direction=direction,
                    remarks=c.remarks,
                )
            )

        return ReconciliationPreviewResponse(
            warehouse_id=wh.id,
            warehouse_code=wh.code,
            warehouse_name=wh.name,
            count_date=payload.count_date,
            count_reference=payload.count_reference,
            total_items_counted=len(payload.counts),
            matched_items_count=matched_count,
            surplus_items_count=surplus_count,
            deficit_items_count=deficit_count,
            variances=variances,
        )

    async def commit_reconciliation_adjustments(
        self,
        user_id: Any,
        payload: ReconciliationCommitRequest,
    ) -> Dict[str, Any]:
        """
        Atomically commits reconciliation variance adjustments.
        - Verifies non-empty reason and warehouse existence.
        - Locks balances deterministically (SELECT ... FOR UPDATE).
        - If all items match (zero variance across all items), returns without adjustments.
        - Posts an atomic ADJUSTMENT transaction via TransactionService.
        - Records an AuditLog entry for the reconciliation event.
        - Commits all changes in one PostgreSQL transaction.
        """
        reason = payload.adjustment_reason.strip()
        if not reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Adjustment reason cannot be empty or whitespace.",
            )

        stmt_wh = select(Warehouse).where(Warehouse.id == payload.warehouse_id)
        res_wh = await self.session.execute(stmt_wh)
        wh = res_wh.scalar_one_or_none()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Warehouse {payload.warehouse_id} not found.",
            )

        item_ids = [c.item_id for c in payload.counts]

        # Fetch items
        stmt_items = select(Item).where(Item.id.in_(item_ids))
        res_items = await self.session.execute(stmt_items)
        items_map = {i.id: i for i in res_items.scalars().all()}

        missing = [i_id for i_id in item_ids if i_id not in items_map]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item {missing[0]} not found in catalog.",
            )

        # Acquire deterministic row locks on inventory balances
        locked_balances = await self.tx_repo.lock_inventory_balances_for_update(
            warehouse_id=payload.warehouse_id,
            item_ids=item_ids,
        )

        lines_to_adjust: List[AdjustmentLineCreate] = []
        for c in payload.counts:
            bal = locked_balances.get(c.item_id)
            current_qty = bal.quantity_on_hand if bal is not None else Decimal("0.0000")
            raw_diff = c.counted_quantity - current_qty

            if raw_diff == Decimal("0"):
                continue

            item = items_map[c.item_id]
            if raw_diff > Decimal("0"):
                direction = "IN"
                qty = raw_diff
            else:
                direction = "OUT"
                qty = abs(raw_diff)
                available = (
                    (bal.quantity_on_hand - bal.quantity_reserved)
                    if bal is not None
                    else Decimal("0.0000")
                )
                if available < qty:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Insufficient stock for downward adjustment of item {item.item_code}. "
                            f"Available: {available}, Required reduction: {qty}"
                        ),
                    )

            lines_to_adjust.append(
                AdjustmentLineCreate(
                    item_id=c.item_id,
                    direction=direction,
                    quantity=qty,
                    unit=item.default_unit,
                    remarks=c.remarks or f"Reconciliation count {payload.count_reference}",
                )
            )

        if not lines_to_adjust:
            return {
                "message": "All counted items match system balances. No adjustments needed.",
                "count_reference": payload.count_reference,
                "transaction_id": None,
                "transaction_number": None,
                "adjusted_lines_count": 0,
                "warehouse_id": str(payload.warehouse_id),
            }

        # Post adjustment transaction
        adj_create = AdjustmentCreate(
            warehouse_id=payload.warehouse_id,
            transaction_date=payload.count_date,
            adjustment_reason=reason,
            remarks=f"Reconciliation count {payload.count_reference}: {reason}",
            lines=lines_to_adjust,
        )
        tx = await self.tx_service.create_and_post_adjustment(
            user_id=user_id,
            payload=adj_create,
        )

        # Record AuditLog for reconciliation event
        await self.tx_repo.create_audit_log(
            actor_user_id=_to_uuid(user_id),
            action="RECONCILIATION",
            entity_type="physical_count",
            entity_id=payload.count_reference,
            before_state=None,
            after_state={
                "warehouse_id": str(payload.warehouse_id),
                "transaction_id": str(tx.id),
                "transaction_number": tx.transaction_number,
                "adjusted_lines_count": len(lines_to_adjust),
                "count_reference": payload.count_reference,
            },
            change_summary=(
                f"Reconciled count {payload.count_reference} for warehouse {payload.warehouse_id} "
                f"via adjustment voucher {tx.transaction_number} ({len(lines_to_adjust)} lines adjusted)."
            ),
            reason=reason,
        )
        await self.session.commit()

        return {
            "message": "Physical count reconciliation adjustments posted successfully.",
            "count_reference": payload.count_reference,
            "transaction_id": str(tx.id),
            "transaction_number": tx.transaction_number,
            "adjusted_lines_count": len(lines_to_adjust),
            "warehouse_id": str(payload.warehouse_id),
        }
