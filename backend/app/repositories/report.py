# backend/app/repositories/report.py
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.category import Category
from app.models.inventory import InventoryBalance
from app.models.item import Item
from app.models.project import Project
from app.models.transaction import (
    StockMovement,
    Transaction,
    TransactionLine,
    TransferLine,
    TransferRecord,
)
from app.models.user import User
from app.models.warehouse import Warehouse


class ReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _build_trial_balance_conditions(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        project_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        transaction_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list:
        conditions = []
        if date_from:
            conditions.append(StockMovement.movement_date >= date_from)
        if date_to:
            conditions.append(StockMovement.movement_date <= date_to)
        if warehouse_id:
            conditions.append(StockMovement.warehouse_id == warehouse_id)
        if project_id:
            conditions.append(
                or_(
                    StockMovement.project_id == project_id,
                    Transaction.project_id == project_id,
                )
            )
        if item_id:
            conditions.append(StockMovement.item_id == item_id)
        if category_id:
            conditions.append(Item.category_id == category_id)
        if transaction_type:
            conditions.append(Transaction.transaction_type == transaction_type)
        if search:
            term = f"%{search}%"
            conditions.append(
                or_(
                    Item.item_code.ilike(term),
                    Item.description.ilike(term),
                    Transaction.transaction_number.ilike(term),
                    Transaction.invoice_no.ilike(term),
                    Transaction.siv_no.ilike(term),
                    Transaction.istv_no.ilike(term),
                    Transaction.plate_no.ilike(term),
                    Transaction.driver_name.ilike(term),
                )
            )
        return conditions

    async def get_trial_balance(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        project_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        transaction_type: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int, Decimal, Decimal]:
        """
        Queries the immutable stock ledger joined with voucher metadata and dimensions.
        Returns: (rows, total_count, total_in, total_out)
        """
        conditions = self._build_trial_balance_conditions(
            date_from=date_from,
            date_to=date_to,
            warehouse_id=warehouse_id,
            project_id=project_id,
            item_id=item_id,
            category_id=category_id,
            transaction_type=transaction_type,
            search=search,
        )

        base_from = (
            select(StockMovement)
            .join(Transaction, StockMovement.transaction_id == Transaction.id)
            .join(
                TransactionLine,
                StockMovement.transaction_line_id == TransactionLine.id,
            )
            .join(Item, StockMovement.item_id == Item.id)
            .join(Category, Item.category_id == Category.id)
            .join(Warehouse, StockMovement.warehouse_id == Warehouse.id)
            .outerjoin(Project, StockMovement.project_id == Project.id)
            .join(User, Transaction.created_by == User.id)
        )

        # 1. Total count
        count_stmt = (
            select(func.count(StockMovement.id))
            .select_from(StockMovement)
            .join(Transaction, StockMovement.transaction_id == Transaction.id)
            .join(Item, StockMovement.item_id == Item.id)
            .join(Warehouse, StockMovement.warehouse_id == Warehouse.id)
        )
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        # 2. Aggregates (total IN and OUT)
        in_expr = func.coalesce(
            func.sum(
                case(
                    (StockMovement.movement_type == "IN", StockMovement.quantity),
                    else_=Decimal("0.0000"),
                )
            ),
            Decimal("0.0000"),
        )
        out_expr = func.coalesce(
            func.sum(
                case(
                    (StockMovement.movement_type == "OUT", StockMovement.quantity),
                    else_=Decimal("0.0000"),
                )
            ),
            Decimal("0.0000"),
        )
        agg_stmt = (
            select(in_expr.label("total_in"), out_expr.label("total_out"))
            .select_from(StockMovement)
            .join(Transaction, StockMovement.transaction_id == Transaction.id)
            .join(Item, StockMovement.item_id == Item.id)
            .join(Warehouse, StockMovement.warehouse_id == Warehouse.id)
        )
        if conditions:
            agg_stmt = agg_stmt.where(and_(*conditions))
        agg_res = (await self.session.execute(agg_stmt)).one()
        total_in = agg_res.total_in
        total_out = agg_res.total_out

        # 3. Paginated details query
        stmt = (
            select(
                StockMovement.id.label("movement_id"),
                StockMovement.movement_date,
                StockMovement.created_at,
                Transaction.id.label("transaction_id"),
                Transaction.transaction_number,
                Transaction.transaction_type,
                Transaction.invoice_no,
                Transaction.received_grv_no,
                Transaction.siv_no,
                Transaction.requested_no,
                Transaction.istv_no,
                Transaction.external_reference,
                Transaction.adjustment_reason,
                Item.id.label("item_id"),
                Item.item_code,
                Item.description.label("item_description"),
                Category.name.label("category_name"),
                TransactionLine.unit,
                Warehouse.id.label("warehouse_id"),
                Warehouse.code.label("warehouse_code"),
                Warehouse.name.label("warehouse_name"),
                Project.name.label("project_name"),
                Transaction.plate_no,
                Transaction.driver_name,
                StockMovement.movement_type,
                StockMovement.quantity,
                StockMovement.signed_quantity,
                StockMovement.running_balance,
                Transaction.status,
                User.full_name.label("entered_by_name"),
            )
            .select_from(StockMovement)
            .join(Transaction, StockMovement.transaction_id == Transaction.id)
            .join(
                TransactionLine,
                StockMovement.transaction_line_id == TransactionLine.id,
            )
            .join(Item, StockMovement.item_id == Item.id)
            .join(Category, Item.category_id == Category.id)
            .join(Warehouse, StockMovement.warehouse_id == Warehouse.id)
            .outerjoin(Project, StockMovement.project_id == Project.id)
            .join(User, Transaction.created_by == User.id)
        )
        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = (
            stmt.order_by(
                StockMovement.movement_date.desc(), StockMovement.created_at.desc()
            )
            .limit(limit)
            .offset(offset)
        )

        res = await self.session.execute(stmt)
        rows = [dict(r._mapping) for r in res.all()]
        return rows, total_count, total_in, total_out

    async def get_all_trial_balance_movements(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        project_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        transaction_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves unpaginated trial balance movements for Excel export."""
        conditions = self._build_trial_balance_conditions(
            date_from=date_from,
            date_to=date_to,
            warehouse_id=warehouse_id,
            project_id=project_id,
            item_id=item_id,
            category_id=category_id,
            transaction_type=transaction_type,
            search=search,
        )

        stmt = (
            select(
                StockMovement.id.label("movement_id"),
                StockMovement.movement_date,
                StockMovement.created_at,
                Transaction.id.label("transaction_id"),
                Transaction.transaction_number,
                Transaction.transaction_type,
                Transaction.invoice_no,
                Transaction.received_grv_no,
                Transaction.siv_no,
                Transaction.requested_no,
                Transaction.istv_no,
                Transaction.external_reference,
                Transaction.adjustment_reason,
                Item.id.label("item_id"),
                Item.item_code,
                Item.description.label("item_description"),
                Category.name.label("category_name"),
                TransactionLine.unit,
                Warehouse.id.label("warehouse_id"),
                Warehouse.code.label("warehouse_code"),
                Warehouse.name.label("warehouse_name"),
                Project.name.label("project_name"),
                Transaction.plate_no,
                Transaction.driver_name,
                StockMovement.movement_type,
                StockMovement.quantity,
                StockMovement.signed_quantity,
                StockMovement.running_balance,
                Transaction.status,
                User.full_name.label("entered_by_name"),
            )
            .select_from(StockMovement)
            .join(Transaction, StockMovement.transaction_id == Transaction.id)
            .join(
                TransactionLine,
                StockMovement.transaction_line_id == TransactionLine.id,
            )
            .join(Item, StockMovement.item_id == Item.id)
            .join(Category, Item.category_id == Category.id)
            .join(Warehouse, StockMovement.warehouse_id == Warehouse.id)
            .outerjoin(Project, StockMovement.project_id == Project.id)
            .join(User, Transaction.created_by == User.id)
        )
        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(
            StockMovement.movement_date.desc(), StockMovement.created_at.desc()
        )
        res = await self.session.execute(stmt)
        return [dict(r._mapping) for r in res.all()]

    async def get_current_stock_balances(
        self,
        warehouse_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries current inventory balances joined with warehouse, project, and catalog info."""
        conditions = []
        if warehouse_id:
            conditions.append(InventoryBalance.warehouse_id == warehouse_id)
        if category_id:
            conditions.append(Item.category_id == category_id)
        if search:
            term = f"%{search}%"
            conditions.append(
                or_(
                    Item.item_code.ilike(term),
                    Item.description.ilike(term),
                    Warehouse.name.ilike(term),
                )
            )

        avail_expr = (
            InventoryBalance.quantity_on_hand - InventoryBalance.quantity_reserved
        ).label("quantity_available")

        stmt = (
            select(
                Warehouse.id.label("warehouse_id"),
                Warehouse.code.label("warehouse_code"),
                Warehouse.name.label("warehouse_name"),
                Project.name.label("project_name"),
                Category.name.label("category_name"),
                Item.id.label("item_id"),
                Item.item_code,
                Item.description.label("item_description"),
                Item.default_unit.label("unit"),
                InventoryBalance.quantity_on_hand,
                InventoryBalance.quantity_reserved,
                avail_expr,
            )
            .select_from(InventoryBalance)
            .join(Warehouse, InventoryBalance.warehouse_id == Warehouse.id)
            .outerjoin(Project, Warehouse.default_project_id == Project.id)
            .join(Item, InventoryBalance.item_id == Item.id)
            .join(Category, Item.category_id == Category.id)
        )
        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(
            Warehouse.code, Category.name, Item.item_code
        )
        res = await self.session.execute(stmt)
        return [dict(r._mapping) for r in res.all()]

    async def get_in_transit_transfers(
        self,
        source_warehouse_id: Optional[uuid.UUID] = None,
        destination_warehouse_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries in-transit transfers with remaining quantity tracking."""
        source_wh = aliased(Warehouse, name="source_wh")
        dest_wh = aliased(Warehouse, name="dest_wh")

        conditions = []
        if source_warehouse_id:
            conditions.append(TransferRecord.source_warehouse_id == source_warehouse_id)
        if destination_warehouse_id:
            conditions.append(
                TransferRecord.destination_warehouse_id == destination_warehouse_id
            )
        if status:
            conditions.append(TransferRecord.status == status)

        remaining_expr = (
            TransferLine.sent_quantity - TransferLine.received_quantity
        ).label("remaining_quantity")

        stmt = (
            select(
                TransferRecord.id.label("transfer_record_id"),
                TransferRecord.istv_transaction_id,
                Transaction.transaction_number.label("istv_number"),
                Transaction.transaction_date,
                source_wh.name.label("source_warehouse_name"),
                dest_wh.name.label("destination_warehouse_name"),
                TransferRecord.plate_no,
                TransferRecord.driver_name,
                TransferRecord.status,
                Item.id.label("item_id"),
                Item.item_code,
                Item.description.label("item_description"),
                Item.default_unit.label("unit"),
                TransferLine.sent_quantity,
                TransferLine.received_quantity,
                remaining_expr,
            )
            .select_from(TransferRecord)
            .join(TransferLine, TransferRecord.id == TransferLine.transfer_record_id)
            .join(Transaction, TransferRecord.istv_transaction_id == Transaction.id)
            .join(source_wh, TransferRecord.source_warehouse_id == source_wh.id)
            .join(dest_wh, TransferRecord.destination_warehouse_id == dest_wh.id)
            .join(Item, TransferLine.item_id == Item.id)
        )
        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(
            Transaction.transaction_date.desc(), TransferRecord.created_at.desc()
        )
        res = await self.session.execute(stmt)
        return [dict(r._mapping) for r in res.all()]
