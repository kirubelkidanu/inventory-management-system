from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.warehouse import WarehouseCreate, WarehouseRead, WarehouseUpdate
from app.security.auth import AuthenticatedUser, get_current_user, require_roles
from app.services.warehouse import WarehouseService

router = APIRouter(prefix="/warehouses", tags=["warehouses"])


async def get_warehouse_service(
    db: AsyncSession = Depends(get_db),
) -> WarehouseService:
    return WarehouseService(db)


@router.post("", response_model=WarehouseRead, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    payload: WarehouseCreate,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: WarehouseService = Depends(get_warehouse_service),
):
    return await service.create_warehouse(payload)


@router.get("", response_model=list[WarehouseRead])
async def list_warehouses(
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: WarehouseService = Depends(get_warehouse_service),
):
    warehouses = await service.list_warehouses()
    return [WarehouseRead.model_validate(warehouse) for warehouse in warehouses]


@router.get("/{warehouse_id}", response_model=WarehouseRead)
async def get_warehouse(
    warehouse_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: WarehouseService = Depends(get_warehouse_service),
):
    warehouse = await service.get_warehouse(warehouse_id)
    return WarehouseRead.model_validate(warehouse)


@router.put("/{warehouse_id}", response_model=WarehouseRead)
async def update_warehouse(
    warehouse_id: UUID,
    payload: WarehouseUpdate,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: WarehouseService = Depends(get_warehouse_service),
):
    warehouse = await service.update_warehouse(warehouse_id, payload)
    return WarehouseRead.model_validate(warehouse)


@router.delete("/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_warehouse(
    warehouse_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: WarehouseService = Depends(get_warehouse_service),
):
    await service.delete_warehouse(warehouse_id)
    return None
