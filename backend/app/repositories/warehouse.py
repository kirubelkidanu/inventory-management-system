from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.warehouse import Warehouse


class WarehouseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Warehouse]:
        result = await self.session.execute(select(Warehouse).order_by(Warehouse.name.asc()))
        return list(result.scalars().all())

    async def get_by_id(self, warehouse_id: UUID) -> Warehouse | None:
        return await self.session.get(Warehouse, warehouse_id)

    async def get_by_code(self, code: str) -> Warehouse | None:
        result = await self.session.execute(select(Warehouse).where(Warehouse.code == code))
        return result.scalar_one_or_none()

    async def get_project_by_id(self, project_id: UUID) -> Project | None:
        return await self.session.get(Project, project_id)

    async def create(self, warehouse: Warehouse) -> Warehouse:
        self.session.add(warehouse)
        await self.session.commit()
        await self.session.refresh(warehouse)
        return warehouse

    async def update(self, warehouse: Warehouse) -> Warehouse:
        await self.session.commit()
        await self.session.refresh(warehouse)
        return warehouse

    async def delete(self, warehouse: Warehouse) -> None:
        await self.session.delete(warehouse)
        await self.session.commit()
