from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.warehouse import Warehouse
from app.repositories.warehouse import WarehouseRepository
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate


class WarehouseService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = WarehouseRepository(session)

    async def list_warehouses(self) -> list[Warehouse]:
        return await self.repository.list()

    async def get_warehouse(self, warehouse_id: UUID) -> Warehouse:
        warehouse = await self.repository.get_by_id(warehouse_id)
        if warehouse is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse not found.",
            )
        return warehouse

    async def create_warehouse(self, payload: WarehouseCreate) -> Warehouse:
        existing = await self.repository.get_by_code(payload.code)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Warehouse code already exists.",
            )

        if payload.default_project_id is not None:
            project = await self.repository.get_project_by_id(payload.default_project_id)
            if project is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="default_project_id references a non-existent project.",
                )

        warehouse = Warehouse(
            code=payload.code,
            name=payload.name,
            location=payload.location,
            default_project_id=payload.default_project_id,
            is_active=payload.is_active,
        )

        try:
            return await self.repository.create(warehouse)
        except IntegrityError:
            await self.repository.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Warehouse could not be created due to a uniqueness constraint.",
            ) from None

    async def update_warehouse(self, warehouse_id: UUID, payload: WarehouseUpdate) -> Warehouse:
        warehouse = await self.get_warehouse(warehouse_id)

        if payload.code is not None and payload.code != warehouse.code:
            existing = await self.repository.get_by_code(payload.code)
            if existing is not None and existing.id != warehouse.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Warehouse code already exists.",
                )
            warehouse.code = payload.code

        if payload.name is not None:
            warehouse.name = payload.name
        if payload.location is not None:
            warehouse.location = payload.location
        if payload.default_project_id is not None and payload.default_project_id != warehouse.default_project_id:
            project = await self.repository.get_project_by_id(payload.default_project_id)
            if project is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="default_project_id references a non-existent project.",
                )
            warehouse.default_project_id = payload.default_project_id
        if payload.is_active is not None:
            warehouse.is_active = payload.is_active

        try:
            return await self.repository.update(warehouse)
        except IntegrityError:
            await self.repository.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Warehouse could not be updated due to a uniqueness constraint.",
            ) from None

    async def delete_warehouse(self, warehouse_id: UUID) -> None:
        warehouse = await self.get_warehouse(warehouse_id)
        await self.repository.delete(warehouse)
