from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item
from app.repositories.item import ItemRepository
from app.schemas.item import (
    ItemBulkDeleteResult,
    ItemCreate,
    ItemDeleteResult,
    ItemUpdate,
)


def _to_uuid(val: Any) -> UUID | None:
    if not val:
        return None
    if isinstance(val, UUID):
        return val
    try:
        return UUID(str(val))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


class ItemService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ItemRepository(session)

    async def list_items(self, include_inactive: bool = False) -> list[Item]:
        return await self.repository.list(include_inactive=include_inactive)

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

    async def delete_item(
        self,
        item_id: UUID,
        actor_user_id: UUID | str | None = None,
    ) -> ItemDeleteResult:
        item = await self.get_item(item_id)
        parsed_user_id = _to_uuid(actor_user_id)

        has_history, balances = await self.repository.check_item_usage(item.id)

        if has_history:
            before_state = {"is_active": item.is_active}
            item.is_active = False
            after_state = {"is_active": False}
            await self.repository.create_audit_log(
                actor_user_id=parsed_user_id,
                action="UPDATE",
                entity_type="item",
                entity_id=str(item.id),
                before_state=before_state,
                after_state=after_state,
                change_summary=f"Soft-archived item {item.item_code} with existing inventory history",
            )
            await self.repository.commit()
            return ItemDeleteResult(
                id=item.id,
                item_code=item.item_code,
                outcome="ARCHIVED",
                message=f"Item {item.item_code} has inventory history or stock and was archived.",
            )
        else:
            if balances:
                await self.repository.delete_zero_balances(item.id)

            before_state = {
                "id": str(item.id),
                "item_code": item.item_code,
                "description": item.description,
                "category_id": str(item.category_id),
                "default_unit": item.default_unit,
                "is_active": item.is_active,
            }
            await self.repository.delete(item)
            await self.repository.create_audit_log(
                actor_user_id=parsed_user_id,
                action="DELETE",
                entity_type="item",
                entity_id=str(item.id),
                before_state=before_state,
                after_state=None,
                change_summary=f"Hard-deleted unused item {item.item_code}",
            )
            await self.repository.commit()
            return ItemDeleteResult(
                id=item.id,
                item_code=item.item_code,
                outcome="DELETED",
                message=f"Item {item.item_code} was permanently deleted.",
            )

    async def bulk_delete_items(
        self,
        item_ids: list[UUID],
        actor_user_id: UUID | str | None = None,
    ) -> ItemBulkDeleteResult:
        parsed_user_id = _to_uuid(actor_user_id)
        deleted_count = 0
        archived_count = 0
        results: list[ItemDeleteResult] = []

        for item_id in item_ids:
            item = await self.repository.get_by_id(item_id)
            if item is None:
                continue

            has_history, balances = await self.repository.check_item_usage(item.id)
            if has_history:
                before_state = {"is_active": item.is_active}
                item.is_active = False
                after_state = {"is_active": False}
                await self.repository.create_audit_log(
                    actor_user_id=parsed_user_id,
                    action="UPDATE",
                    entity_type="item",
                    entity_id=str(item.id),
                    before_state=before_state,
                    after_state=after_state,
                    change_summary=f"Soft-archived item {item.item_code} with existing inventory history",
                )
                archived_count += 1
                results.append(
                    ItemDeleteResult(
                        id=item.id,
                        item_code=item.item_code,
                        outcome="ARCHIVED",
                        message=f"Item {item.item_code} has inventory history or stock and was archived.",
                    )
                )
            else:
                if balances:
                    await self.repository.delete_zero_balances(item.id)

                before_state = {
                    "id": str(item.id),
                    "item_code": item.item_code,
                    "description": item.description,
                    "category_id": str(item.category_id),
                    "default_unit": item.default_unit,
                    "is_active": item.is_active,
                }
                await self.repository.delete(item)
                await self.repository.create_audit_log(
                    actor_user_id=parsed_user_id,
                    action="DELETE",
                    entity_type="item",
                    entity_id=str(item.id),
                    before_state=before_state,
                    after_state=None,
                    change_summary=f"Hard-deleted unused item {item.item_code}",
                )
                deleted_count += 1
                results.append(
                    ItemDeleteResult(
                        id=item.id,
                        item_code=item.item_code,
                        outcome="DELETED",
                        message=f"Item {item.item_code} was permanently deleted.",
                    )
                )

        await self.repository.commit()
        return ItemBulkDeleteResult(
            deleted_count=deleted_count,
            archived_count=archived_count,
            results=results,
        )

    async def restore_item(
        self,
        item_id: UUID,
        actor_user_id: UUID | str | None = None,
    ) -> Item:
        item = await self.get_item(item_id)
        parsed_user_id = _to_uuid(actor_user_id)

        before_state = {"is_active": item.is_active}
        item.is_active = True
        after_state = {"is_active": True}

        await self.repository.create_audit_log(
            actor_user_id=parsed_user_id,
            action="UPDATE",
            entity_type="item",
            entity_id=str(item.id),
            before_state=before_state,
            after_state=after_state,
            change_summary=f"Restored item {item.item_code} to active catalog",
        )
        await self.repository.commit()
        await self.repository.session.refresh(item)
        return item
