from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.category import CategoryCreate, CategoryRead, CategoryStatusUpdate, CategoryUpdate
from app.security.auth import AuthenticatedUser, get_current_user, require_roles
from app.services.category import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


async def get_category_service(
    db: AsyncSession = Depends(get_db),
) -> CategoryService:
    return CategoryService(db)


def _get_user_id(user: AuthenticatedUser) -> Optional[UUID]:
    raw = getattr(user, "id", None) or getattr(user, "user_id", None)
    if raw is None:
        return None
    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(str(raw))
    except (ValueError, TypeError):
        return None


@router.get("/", response_model=list[CategoryRead], include_in_schema=False)
@router.get("", response_model=list[CategoryRead], summary="List item categories with item counts")
async def list_categories(
    include_archived: bool = Query(default=False, description="Include archived/inactive categories"),
    search: Optional[str] = Query(default=None, description="Search term for category code or name"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: CategoryService = Depends(get_category_service),
):
    categories = await service.list_categories(
        include_archived=include_archived,
        search=search,
    )
    return [CategoryRead.model_validate(category) for category in categories]


@router.post("/", response_model=CategoryRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED, summary="Create a new category (Admin only)")
async def create_category(
    payload: CategoryCreate,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN")),
    service: CategoryService = Depends(get_category_service),
):
    user_id = _get_user_id(current_user)
    category = await service.create_category(payload, user_id=user_id)
    return CategoryRead.model_validate(category)


@router.get("/{category_id}/", response_model=CategoryRead, include_in_schema=False)
@router.get("/{category_id}", response_model=CategoryRead, summary="Get category by ID")
async def get_category(
    category_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: CategoryService = Depends(get_category_service),
):
    category = await service.get_category(category_id)
    return CategoryRead.model_validate(category)


@router.put("/{category_id}/", response_model=CategoryRead, include_in_schema=False)
@router.put("/{category_id}", response_model=CategoryRead, summary="Update category (Admin only)")
async def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN")),
    service: CategoryService = Depends(get_category_service),
):
    user_id = _get_user_id(current_user)
    updated = await service.update_category(category_id, payload, user_id=user_id)
    return CategoryRead.model_validate(updated)


@router.patch("/{category_id}/status/", response_model=CategoryRead, include_in_schema=False)
@router.patch("/{category_id}/status", response_model=CategoryRead, summary="Toggle or set category active status (Admin only)")
async def toggle_category_status(
    category_id: UUID,
    payload: Optional[CategoryStatusUpdate] = None,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN")),
    service: CategoryService = Depends(get_category_service),
):
    user_id = _get_user_id(current_user)
    is_active = payload.is_active if payload else None
    updated = await service.toggle_status(category_id, is_active=is_active, user_id=user_id)
    return CategoryRead.model_validate(updated)


@router.delete("/{category_id}/", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Archive category (Admin only)")
async def delete_category(
    category_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN")),
    service: CategoryService = Depends(get_category_service),
):
    user_id = _get_user_id(current_user)
    await service.delete_category(category_id, user_id=user_id)
    return None
