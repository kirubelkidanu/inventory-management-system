from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item
from app.repositories.item import ItemRepository
from app.schemas.item import ItemCreate, ItemUpdate


class ItemService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ItemRepository(session)

    async def list_items(self) -> list[Item]:
        return await self.repository.list()

    async def get_item(self, item_id: UUID) -> Item:
        item = await self.repository.get_by_id(item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found.",
            )
        return item

    async def create_item(self, payload: ItemCreate) -> Item:
        existing = await self.repository.get_by_code(payload.item_code)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Item code already exists.",
            )

        category = await self.repository.get_category_by_id(payload.category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="category_id references a non-existent category.",
            )

        item = Item(
            item_code=payload.item_code,
            description=payload.description,
            category_id=payload.category_id,
            default_unit=payload.default_unit,
            is_active=payload.is_active,
        )

        try:
            return await self.repository.create(item)
        except IntegrityError:
            await self.repository.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Item could not be created due to a uniqueness constraint.",
            ) from None

    async def update_item(self, item_id: UUID, payload: ItemUpdate) -> Item:
        item = await self.get_item(item_id)

        if payload.description is not None:
            item.description = payload.description
        if payload.category_id is not None and payload.category_id != item.category_id:
            category = await self.repository.get_category_by_id(payload.category_id)
            if category is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="category_id references a non-existent category.",
                )
            item.category_id = payload.category_id
        if payload.default_unit is not None:
            item.default_unit = payload.default_unit
        if payload.is_active is not None:
            item.is_active = payload.is_active

        try:
            return await self.repository.update(item)
        except IntegrityError:
            await self.repository.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Item could not be updated due to a uniqueness constraint.",
            ) from None

    async def delete_item(self, item_id: UUID) -> None:
        item = await self.get_item(item_id)
        await self.repository.delete(item)
