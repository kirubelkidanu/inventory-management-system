from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.item import Item


class ItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Item]:
        result = await self.session.execute(select(Item).order_by(Item.item_code.asc()))
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
        await self.session.commit()
