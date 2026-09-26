from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Category]:
        result = await self.session.execute(select(Category).order_by(Category.name.asc()))
        return list(result.scalars().all())

    async def get_by_id(self, category_id: UUID) -> Category | None:
        return await self.session.get(Category, category_id)

    async def get_by_code(self, code: str) -> Category | None:
        result = await self.session.execute(select(Category).where(Category.code == code))
        return result.scalar_one_or_none()

    async def create(self, category: Category) -> Category:
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def update(self, category: Category) -> Category:
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def delete(self, category: Category) -> None:
        await self.session.delete(category)
        await self.session.commit()
