from __future__ import annotations

from typing import Optional
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

    async def list_categories(
        self,
        include_archived: bool = False,
        search: Optional[str] = None,
    ) -> list[Category]:
        return await self.repository.get_categories(
            include_archived=include_archived,
            search=search,
        )

    async def get_category(self, category_id: UUID) -> Category:
        category = await self.repository.get_by_id(category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )
        return category

    async def create_category(
        self,
        payload: CategoryCreate,
        user_id: Optional[UUID] = None,
    ) -> Category:
        clean_code = payload.code.strip().upper()
        existing = await self.repository.get_by_code(clean_code)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category code '{clean_code}' already exists.",
            )

        category = Category(
            code=clean_code,
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
            is_active=payload.is_active,
        )

        try:
            created = await self.repository.create(category)
        except IntegrityError:
            await self.repository.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category could not be created due to a uniqueness constraint.",
            ) from None

        # Record compliant audit log (action='CREATE')
        try:
            await self.repository.create_audit_log(
                actor_user_id=user_id,
                action="CREATE",
                entity_type="category",
                entity_id=str(created.id),
                before_state=None,
                after_state={
                    "id": str(created.id),
                    "code": created.code,
                    "name": created.name,
                    "description": created.description,
                    "is_active": created.is_active,
                },
                change_summary=f"Created category '{created.code}' ({created.name})",
                reason="Admin Category Creation",
            )
        except Exception:
            pass

        return created

    async def update_category(
        self,
        category_id: UUID,
        payload: CategoryUpdate,
        user_id: Optional[UUID] = None,
    ) -> Category:
        category = await self.get_category(category_id)
        before_state = {
            "id": str(category.id),
            "code": category.code,
            "name": category.name,
            "description": category.description,
            "is_active": category.is_active,
        }

        if payload.code is not None and payload.code.strip().upper() != category.code:
            clean_code = payload.code.strip().upper()
            existing = await self.repository.get_by_code(clean_code)
            if existing is not None and existing.id != category.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Category code '{clean_code}' already exists.",
                )
            category.code = clean_code

        warning_note = None
        if payload.is_active is False and category.is_active is True:
            # Check if category has active items
            active_items = await self.repository.get_active_items_count(category.id)
            if active_items > 0:
                warning_note = f"Warning: Category has {active_items} active item(s)."

        if payload.name is not None:
            category.name = payload.name.strip()
        if payload.description is not None:
            category.description = payload.description.strip() if payload.description else None
        if payload.is_active is not None:
            category.is_active = payload.is_active

        try:
            updated = await self.repository.update(category)
        except IntegrityError:
            await self.repository.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category could not be updated due to a uniqueness constraint.",
            ) from None

        # Record compliant audit log (action='UPDATE')
        try:
            await self.repository.create_audit_log(
                actor_user_id=user_id,
                action="UPDATE",
                entity_type="category",
                entity_id=str(updated.id),
                before_state=before_state,
                after_state={
                    "id": str(updated.id),
                    "code": updated.code,
                    "name": updated.name,
                    "description": updated.description,
                    "is_active": updated.is_active,
                },
                change_summary=f"Updated category '{updated.code}'" + (f" ({warning_note})" if warning_note else ""),
                reason=warning_note or "Admin Category Update",
            )
        except Exception:
            pass

        return updated

    async def toggle_status(
        self,
        category_id: UUID,
        is_active: Optional[bool] = None,
        user_id: Optional[UUID] = None,
    ) -> Category:
        category = await self.get_category(category_id)
        new_status = not category.is_active if is_active is None else is_active
        return await self.update_category(
            category_id,
            CategoryUpdate(is_active=new_status),
            user_id=user_id,
        )

    async def delete_category(
        self,
        category_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> None:
        """
        Soft-archives category to preserve referential integrity on items.category_id (ON DELETE RESTRICT).
        """
        await self.update_category(
            category_id,
            CategoryUpdate(is_active=False),
            user_id=user_id,
        )
