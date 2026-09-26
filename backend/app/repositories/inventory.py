from typing import List, Optional
import uuid

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryBalance
from app.models.item import Item
from app.models.transaction import StockMovement


class InventoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.db = session

    async def get_balance_by_item_warehouse(
        self,
        warehouse_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> Optional[InventoryBalance]:
        stmt = select(InventoryBalance).where(
            InventoryBalance.warehouse_id == warehouse_id,
            InventoryBalance.item_id == item_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_balances(
        self,
        warehouse_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
    ) -> List[InventoryBalance]:
        stmt = select(InventoryBalance)
        if category_id or search:
            stmt = stmt.join(Item, InventoryBalance.item_id == Item.id)
            if category_id:
                stmt = stmt.where(Item.category_id == category_id)
            if search:
                search_term = f"%{search}%"
                stmt = stmt.where(
                    or_(
                        Item.item_code.ilike(search_term),
                        Item.description.ilike(search_term),
                    )
                )
        if warehouse_id:
            stmt = stmt.where(InventoryBalance.warehouse_id == warehouse_id)
        if item_id:
            stmt = stmt.where(InventoryBalance.item_id == item_id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_stock_movements(
        self,
        warehouse_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
    ) -> List[StockMovement]:
        stmt = select(StockMovement)
        if warehouse_id:
            stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
        if item_id:
            stmt = stmt.where(StockMovement.item_id == item_id)
        stmt = stmt.order_by(StockMovement.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_reconciliation_discrepancies(self) -> List[dict]:
        stmt = text("SELECT * FROM vw_reconciliation_discrepancies")
        result = await self.session.execute(stmt)
        return [dict(row) for row in result.mappings().all()]