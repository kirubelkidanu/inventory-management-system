from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate
from app.security.auth import AuthenticatedUser, get_current_user, require_roles
from app.services.item import ItemService

router = APIRouter(prefix="/items", tags=["items"])


async def get_item_service(
    db: AsyncSession = Depends(get_db),
) -> ItemService:
    return ItemService(db)


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: ItemService = Depends(get_item_service),
):
    return await service.create_item(payload)


@router.get("", response_model=list[ItemRead])
async def list_items(
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ItemService = Depends(get_item_service),
):
    items = await service.list_items()
    return [ItemRead.model_validate(item) for item in items]


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(
    item_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ItemService = Depends(get_item_service),
):
    item = await service.get_item(item_id)
    return ItemRead.model_validate(item)


@router.put("/{item_id}", response_model=ItemRead)
async def update_item(
    item_id: UUID,
    payload: ItemUpdate,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: ItemService = Depends(get_item_service),
):
    item = await service.update_item(item_id, payload)
    return ItemRead.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: ItemService = Depends(get_item_service),
):
    await service.delete_item(item_id)
    return None
