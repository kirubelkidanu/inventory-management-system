from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.security.auth import AuthenticatedUser, get_current_user, require_roles
from app.services.project import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


async def get_project_service(
    db: AsyncSession = Depends(get_db),
) -> ProjectService:
    return ProjectService(db)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: ProjectService = Depends(get_project_service),
):
    return await service.create_project(payload)


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    projects = await service.list_projects()
    return [ProjectRead.model_validate(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    project = await service.get_project(project_id)
    return ProjectRead.model_validate(project)


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: ProjectService = Depends(get_project_service),
):
    project = await service.update_project(project_id, payload)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "INVENTORY_MANAGER")),
    service: ProjectService = Depends(get_project_service),
):
    await service.delete_project(project_id)
    return None
