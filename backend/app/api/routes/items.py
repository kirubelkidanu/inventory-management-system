from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.item import (
    ItemBulkDeleteRequest,
    ItemBulkDeleteResult,
    ItemCreate,
    ItemDeleteResult,
    ItemRead,
    ItemUpdate,
    ItemLatestCostResponse,
)
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
    return await service.create_item(payload, actor_user_id=current_user.user_id)


@router.get("", response_model=list[ItemRead])
async def list_items(
    response: Response,
    search: str | None = Query(None),
    category_id: UUID | None = Query(None),
    include_inactive: bool = Query(False),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=2000),
    page_size: int | None = Query(None, ge=1, le=2000),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ItemService = Depends(get_item_service),
):
    eff_limit = limit if limit is not None else page_size
    eff_include_inactive = include_inactive
    if is_active is not None:
        eff_include_inactive = not is_active

    if hasattr(service, "list_items_with_count"):
        items, total = await service.list_items_with_count(
            search=search,
            category_id=category_id,
            include_inactive=eff_include_inactive,
            skip=skip,
            limit=eff_limit,
        )
    else:
        items = await service.list_items(include_inactive=eff_include_inactive)
        total = len(items)

    prices = {}
    if hasattr(service, "get_latest_unit_prices_batch"):
        item_ids = [item.id for item in items]
        prices = await service.get_latest_unit_prices_batch(item_ids)
    elif hasattr(service, "repository") and hasattr(service.repository, "get_latest_unit_prices_batch"):
        item_ids = [item.id for item in items]
        prices = await service.repository.get_latest_unit_prices_batch(item_ids)

    result_dtos = []
    for item in items:
        dto = ItemRead.model_validate(item)
        if item.id in prices:
            dto.latest_unit_price = prices[item.id]
        elif hasattr(item, "latest_unit_price") and item.latest_unit_price is not None:
            dto.latest_unit_price = item.latest_unit_price
        result_dtos.append(dto)

    response.headers["X-Total-Count"] = str(total)
    return result_dtos


@router.post("/bulk-delete", response_model=ItemBulkDeleteResult)
async def bulk_delete_items(
    payload: ItemBulkDeleteRequest,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN")),
    service: ItemService = Depends(get_item_service),
):
    return await service.bulk_delete_items(
        item_ids=payload.item_ids,
        actor_user_id=current_user.user_id,
    )


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(
    item_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ItemService = Depends(get_item_service),
):
    item = await service.get_item(item_id)
    dto = ItemRead.model_validate(item)
    if hasattr(service, "get_latest_unit_price"):
        dto.latest_unit_price = await service.get_latest_unit_price(item_id)
    return dto


@router.get("/{item_id}/latest-cost", response_model=ItemLatestCostResponse)
@router.get("/{item_id}/latest-cost/", response_model=ItemLatestCostResponse, include_in_schema=False)
async def get_item_latest_cost(
    item_id: UUID,
    warehouse_id: UUID | None = Query(None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ItemService = Depends(get_item_service),
):
    price = None
    if hasattr(service, "get_latest_unit_price"):
        price = await service.get_latest_unit_price(item_id, warehouse_id=warehouse_id)
    return ItemLatestCostResponse(item_id=item_id, latest_unit_price=price)


@router.put("/{item_id}", response_model=ItemRead)
async def update_item(
    item_id: UUID,
    payload: ItemUpdate,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: ItemService = Depends(get_item_service),
):
    item = await service.update_item(
        item_id=item_id,
        payload=payload,
        actor_user_id=current_user.user_id,
    )
    return ItemRead.model_validate(item)


@router.delete("/{item_id}", response_model=ItemDeleteResult)
async def delete_item(
    item_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN")),
    service: ItemService = Depends(get_item_service),
):
    return await service.delete_item(
        item_id=item_id,
        actor_user_id=current_user.user_id,
    )


@router.patch("/{item_id}/restore", response_model=ItemRead)
async def restore_item(
    item_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN")),
    service: ItemService = Depends(get_item_service),
):
    item = await service.restore_item(
        item_id=item_id,
        actor_user_id=current_user.user_id,
    )
    return ItemRead.model_validate(item)
