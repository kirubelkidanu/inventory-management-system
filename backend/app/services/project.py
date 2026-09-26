from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.repositories.project import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ProjectRepository(session)

    async def list_projects(self) -> list[Project]:
        return await self.repository.list()

    async def get_project(self, project_id: UUID) -> Project:
        project = await self.repository.get_by_id(project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )
        return project

    async def create_project(self, payload: ProjectCreate) -> Project:
        existing = await self.repository.get_by_code(payload.code)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project code already exists.",
            )

        project = Project(
            code=payload.code,
            name=payload.name,
            location=payload.location,
            is_active=payload.is_active,
        )

        try:
            return await self.repository.create(project)
        except IntegrityError:
            await self.repository.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project could not be created due to a uniqueness constraint.",
            ) from None

    async def update_project(self, project_id: UUID, payload: ProjectUpdate) -> Project:
        project = await self.get_project(project_id)

        if payload.code is not None and payload.code != project.code:
            existing = await self.repository.get_by_code(payload.code)
            if existing is not None and existing.id != project.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Project code already exists.",
                )
            project.code = payload.code

        if payload.name is not None:
            project.name = payload.name
        if payload.location is not None:
            project.location = payload.location
        if payload.is_active is not None:
            project.is_active = payload.is_active

        try:
            return await self.repository.update(project)
        except IntegrityError:
            await self.repository.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project could not be updated due to a uniqueness constraint.",
            ) from None

    async def delete_project(self, project_id: UUID) -> None:
        project = await self.get_project(project_id)
        await self.repository.delete(project)
