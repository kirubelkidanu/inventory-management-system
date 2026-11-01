from typing import List, Optional
import uuid

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.inventory import InventoryBalance
from app.models.item import Item
from app.models.transaction import StockMovement
from app.models.warehouse import Warehouse


class InventoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.db = session

    async def get_balance_by_item_warehouse(
        self,
        warehouse_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> Optional[dict]:
        stmt = (
            select(
                InventoryBalance.id,
                InventoryBalance.warehouse_id,
                InventoryBalance.item_id,
                InventoryBalance.quantity_on_hand,
                InventoryBalance.quantity_reserved,
                InventoryBalance.updated_at,
                Item.item_code.label("item_code"),
                Item.description.label("item_description"),
                Item.default_unit.label("unit"),
                Category.name.label("category_name"),
                Warehouse.code.label("warehouse_code"),
                Warehouse.name.label("warehouse_name"),
                Warehouse.is_active.label("warehouse_is_active"),
            )
            .join(Item, InventoryBalance.item_id == Item.id)
            .join(Warehouse, InventoryBalance.warehouse_id == Warehouse.id)
            .outerjoin(Category, Item.category_id == Category.id)
            .where(
                InventoryBalance.warehouse_id == warehouse_id,
                InventoryBalance.item_id == item_id,
            )
        )
        result = await self.session.execute(stmt)
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_balances(
        self,
        warehouse_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
        include_inactive_warehouses: bool = False,
    ) -> List[dict]:
        stmt = (
            select(
                InventoryBalance.id,
                InventoryBalance.warehouse_id,
                InventoryBalance.item_id,
                InventoryBalance.quantity_on_hand,
                InventoryBalance.quantity_reserved,
                InventoryBalance.updated_at,
                Item.item_code.label("item_code"),
                Item.description.label("item_description"),
                Item.default_unit.label("unit"),
                Category.name.label("category_name"),
                Warehouse.code.label("warehouse_code"),
                Warehouse.name.label("warehouse_name"),
                Warehouse.is_active.label("warehouse_is_active"),
            )
            .join(Item, InventoryBalance.item_id == Item.id)
            .join(Warehouse, InventoryBalance.warehouse_id == Warehouse.id)
            .outerjoin(Category, Item.category_id == Category.id)
        )

        if warehouse_id:
            stmt = stmt.where(InventoryBalance.warehouse_id == warehouse_id)
        elif not include_inactive_warehouses:
            # By default exclude archived/inactive warehouses unless specifically filtered
            stmt = stmt.where(Warehouse.is_active.is_(True))

        if item_id:
            stmt = stmt.where(InventoryBalance.item_id == item_id)

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

        stmt = stmt.order_by(Warehouse.name.asc(), Item.item_code.asc())
        result = await self.session.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

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
