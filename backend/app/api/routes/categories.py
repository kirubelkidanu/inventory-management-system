from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.security.auth import AuthenticatedUser, get_current_user, require_roles
from app.services.category import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


async def get_category_service(
    db: AsyncSession = Depends(get_db),
) -> CategoryService:
    return CategoryService(db)


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: CategoryService = Depends(get_category_service),
):
    return await service.create_category(payload)


@router.get("", response_model=list[CategoryRead])
async def list_categories(
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: CategoryService = Depends(get_category_service),
):
    categories = await service.list_categories()
    return [CategoryRead.model_validate(category) for category in categories]


@router.get("/{category_id}", response_model=CategoryRead)
async def get_category(
    category_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: CategoryService = Depends(get_category_service),
):
    category = await service.get_category(category_id)
    return CategoryRead.model_validate(category)


@router.put("/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: CategoryService = Depends(get_category_service),
):
    new_category = await service.update_category(category_id, payload)
    return CategoryRead.model_validate(new_category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: CategoryService = Depends(get_category_service),
):
    await service.delete_category(category_id)
    return None
