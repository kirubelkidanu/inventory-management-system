from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.category import Category
from app.models.inventory import InventoryBalance
from app.models.item import Item
from app.models.transaction import StockMovement, TransactionLine, TransferLine


class ItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, include_inactive: bool = False) -> list[Item]:
        stmt = select(Item)
        if not include_inactive:
            stmt = stmt.where(Item.is_active.is_(True))
        result = await self.session.execute(stmt.order_by(Item.item_code.asc()))
        return list(result.scalars().all())

    async def get_by_id(self, item_id: UUID) -> Item | None:
        return await self.session.get(Item, item_id)

    async def get_by_code(self, item_code: str) -> Item | None:
        result = await self.session.execute(select(Item).where(Item.item_code == item_code))
        return result.scalar_one_or_none()

    async def get_category_by_id(self, category_id: UUID) -> Category | None:
        return await self.session.get(Category, category_id)

    async def create(self, item: Item) -> Item:
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update(self, item: Item) -> Item:
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def delete(self, item: Item) -> None:
        await self.session.delete(item)

    async def check_item_usage(self, item_id: UUID) -> tuple[bool, list[InventoryBalance]]:
        """
        Check if the item is referenced in transaction lines, stock movements,
        or transfer lines, or has non-zero inventory balances.
        Returns (has_history_or_stock, balances).
        """
        tx_count_res = await self.session.execute(
            select(func.count(TransactionLine.id)).where(TransactionLine.item_id == item_id)
        )
        tx_count = tx_count_res.scalar_one() or 0

        sm_count_res = await self.session.execute(
            select(func.count(StockMovement.id)).where(StockMovement.item_id == item_id)
        )
        sm_count = sm_count_res.scalar_one() or 0

        tl_count_res = await self.session.execute(
            select(func.count(TransferLine.id)).where(TransferLine.item_id == item_id)
        )
        tl_count = tl_count_res.scalar_one() or 0

        bal_res = await self.session.execute(
            select(InventoryBalance).where(InventoryBalance.item_id == item_id)
        )
        balances = list(bal_res.scalars().all())

        has_stock = any(b.quantity_on_hand > 0 or b.quantity_reserved > 0 for b in balances)
        has_history = (tx_count > 0) or (sm_count > 0) or (tl_count > 0)

        return (has_history or has_stock, balances)

    async def delete_zero_balances(self, item_id: UUID) -> None:
        await self.session.execute(
            delete(InventoryBalance).where(InventoryBalance.item_id == item_id)
        )

    async def create_audit_log(
        self,
        actor_user_id: Optional[UUID],
        action: str,
        entity_type: str,
        entity_id: str,
        before_state: Optional[dict] = None,
        after_state: Optional[dict] = None,
        change_summary: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> AuditLog:
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

    async def commit(self) -> None:
        await self.session.commit()
