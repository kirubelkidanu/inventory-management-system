from typing import List, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.inventory import (
    InventoryBalanceRead,
    ReconciliationData,
    StockMovementRead,
)
from app.repositories.inventory import InventoryRepository


class InventoryService:
    def __init__(self, db: AsyncSession):
        self.session = db
        self.repo = InventoryRepository(db)

    async def get_inventory_balance(
        self,
        warehouse_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> Optional[InventoryBalanceRead]:
        balance = await self.repo.get_balance_by_item_warehouse(
            warehouse_id,
            item_id,
        )

        if balance:
            return InventoryBalanceRead.model_validate(balance)

        return None

    async def get_all_balances(
        self,
        warehouse_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
    ) -> List[InventoryBalanceRead]:
        balances = await self.repo.list_balances(
            warehouse_id=warehouse_id,
            item_id=item_id,
            category_id=category_id,
            search=search,
        )
        return [
            InventoryBalanceRead.model_validate(balance)
            for balance in balances
        ]

    async def get_stock_movements(
        self,
        warehouse_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
    ) -> List[StockMovementRead]:
        movements = await self.repo.list_stock_movements(
            warehouse_id,
            item_id,
        )

        return [
            StockMovementRead.model_validate(movement)
            for movement in movements
        ]

    async def get_reconciliation_data(self) -> List[ReconciliationData]:
        rows = await self.repo.list_reconciliation_discrepancies()
        return [
            ReconciliationData(
                warehouse_id=row["warehouse_id"],
                warehouse_code=row["warehouse_code"],
                warehouse_name=row["warehouse_name"],
                item_id=row["item_id"],
                item_code=row["item_code"],
                item_description=row["item_description"],
                projected_balance=float(row["projected_balance"]),
                ledger_cumulative_balance=float(row["ledger_cumulative_balance"]),
                discrepancy=float(row["discrepancy"]),
            )
            if isinstance(row, dict) else ReconciliationData.model_validate(row)
            for row in rows
        ]