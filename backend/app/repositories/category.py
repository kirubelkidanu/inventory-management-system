from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.category import Category
from app.models.item import Item


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_categories(
        self,
        include_archived: bool = False,
        search: Optional[str] = None,
    ) -> list[Category]:
        """
        Retrieves categories left-joined with items to compute active item_count.
        Supports filtering by archived status and searching by code/name.
        """
        stmt = (
            select(Category, func.count(Item.id).label("item_count"))
            .outerjoin(Item, (Item.category_id == Category.id) & (Item.is_active == True))
            .group_by(Category.id)
            .order_by(Category.code.asc())
        )
        if not include_archived:
            stmt = stmt.where(Category.is_active == True)
        if search:
            term = f"%{search.strip().upper()}%"
            stmt = stmt.where(or_(func.upper(Category.code).like(term), func.upper(Category.name).like(term)))

        result = await self.session.execute(stmt)
        rows = result.all()
        categories: list[Category] = []
        for cat, count in rows:
            cat.item_count = count
            categories.append(cat)
        return categories

    async def list(self) -> list[Category]:
        """List active categories (alias for get_categories)."""
        return await self.get_categories(include_archived=False)

    async def get_by_id(self, category_id: UUID) -> Category | None:
        stmt = (
            select(Category, func.count(Item.id).label("item_count"))
            .outerjoin(Item, (Item.category_id == Category.id) & (Item.is_active == True))
            .where(Category.id == category_id)
            .group_by(Category.id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row:
            cat, count = row
            cat.item_count = count
            return cat
        return None

    async def get_by_code(self, code: str) -> Category | None:
        clean = code.strip().upper()
        result = await self.session.execute(
            select(Category).where(func.upper(Category.code) == clean)
        )
        return result.scalar_one_or_none()

    async def create(self, category: Category) -> Category:
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        category.item_count = 0
        return category

    async def update(self, category: Category) -> Category:
        category.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(category)
        if not hasattr(category, "item_count"):
            category.item_count = await self.get_active_items_count(category.id)
        return category

    async def delete(self, category: Category) -> None:
        await self.session.delete(category)
        await self.session.commit()

    async def get_active_items_count(self, category_id: UUID) -> int:
        stmt = select(func.count(Item.id)).where(Item.category_id == category_id, Item.is_active == True)
        res = await self.session.execute(stmt)
        return res.scalar() or 0

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
        await self.session.commit()
        return audit_log
