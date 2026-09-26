from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = CategoryRepository(session)

    async def list_categories(self) -> list[Category]:
        return await self.repository.list()

    async def get_category(self, category_id: UUID) -> Category:
        category = await self.repository.get_by_id(category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )
        return category

    async def create_category(self, payload: CategoryCreate) -> Category:
        existing = await self.repository.get_by_code(payload.code)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category code already exists.",
            )

        category = Category(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            is_active=payload.is_active,
        )

        try:
            return await self.repository.create(category)
        except IntegrityError:
            await self.repository.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category could not be created due to a uniqueness constraint.",
            ) from None

    async def update_category(self, category_id: UUID, payload: CategoryUpdate) -> Category:
        category = await self.get_category(category_id)

        if payload.code is not None and payload.code != category.code:
            existing = await self.repository.get_by_code(payload.code)
            if existing is not None and existing.id != category.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Category code already exists.",
                )
            category.code = payload.code

        if payload.name is not None:
            category.name = payload.name
        if payload.description is not None:
            category.description = payload.description
        if payload.is_active is not None:
            category.is_active = payload.is_active

        try:
            return await self.repository.update(category)
        except IntegrityError:
            await self.repository.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category could not be updated due to a uniqueness constraint.",
            ) from None

    async def delete_category(self, category_id: UUID) -> None:
        category = await self.get_category(category_id)
        await self.repository.delete(category)
