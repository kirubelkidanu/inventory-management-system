from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Project]:
        result = await self.session.execute(select(Project).order_by(Project.name.asc()))
        return list(result.scalars().all())

    async def get_by_id(self, project_id: UUID) -> Project | None:
        return await self.session.get(Project, project_id)

    async def get_by_code(self, code: str) -> Project | None:
        result = await self.session.execute(select(Project).where(Project.code == code))
        return result.scalar_one_or_none()

    async def create(self, project: Project) -> Project:
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def update(self, project: Project) -> Project:
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete(self, project: Project) -> None:
        await self.session.delete(project)
        await self.session.commit()
