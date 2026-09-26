from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.api.routes.projects import get_project_service
from app.core.config import settings
from app.main import app
from app.models.project import Project


class FakeProjectService:
    def __init__(self):
        self.store: dict[str, Project] = {}

    async def list_projects(self):
        return list(self.store.values())

    async def get_project(self, project_id):
        project = self.store.get(str(project_id))
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return project

    async def create_project(self, payload):
        if any(item.code == payload.code for item in self.store.values()):
            raise HTTPException(status_code=409, detail="Project code already exists.")
        project = Project(
            id=uuid4(),
            code=payload.code,
            name=payload.name,
            location=payload.location,
            is_active=payload.is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.store[str(project.id)] = project
        return project

    async def update_project(self, project_id, payload):
        project = await self.get_project(project_id)
        if payload.code is not None and payload.code != project.code:
            if any(item.code == payload.code for item in self.store.values() if item.id != project.id):
                raise HTTPException(status_code=409, detail="Project code already exists.")
            project.code = payload.code
        if payload.name is not None:
            project.name = payload.name
        if payload.location is not None:
            project.location = payload.location
        if payload.is_active is not None:
            project.is_active = payload.is_active
        project.updated_at = datetime.now(timezone.utc)
        return project

    async def delete_project(self, project_id):
        project = await self.get_project(project_id)
        self.store.pop(str(project.id), None)


@pytest.fixture
def token_factory():
    def make_token(role: str = "ADMIN", user_id: str = "user-123") -> str:
        return jwt.encode(
            {
                "sub": user_id,
                "email": f"{user_id}@example.com",
                "role": role,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )

    return make_token


@pytest.fixture
def fake_service():
    return FakeProjectService()


@pytest.mark.asyncio
async def test_project_routes_are_registered():
    assert app.url_path_for("list_projects") == "/api/v1/projects"
    assert app.url_path_for("get_project", project_id="123") == "/api/v1/projects/123"


@pytest.mark.asyncio
async def test_project_routes_require_auth(token_factory, fake_service):
    app.dependency_overrides[get_project_service] = lambda: fake_service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/projects")
    app.dependency_overrides.clear()
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_project_routes_authorize_existing_roles(token_factory, fake_service):
    app.dependency_overrides[get_project_service] = lambda: fake_service
    token = token_factory(role="VIEWER")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/projects",
            json={"code": "PRJ-TEST", "name": "Test Project", "location": "HQ"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_project(token_factory, fake_service):
    app.dependency_overrides[get_project_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/projects",
            json={"code": "PRJ-ADMIN", "name": "Admin Project", "location": "Addis"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "PRJ-ADMIN"
    assert body["name"] == "Admin Project"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_list_projects(token_factory, fake_service):
    app.dependency_overrides[get_project_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_project(token_factory, fake_service):
    app.dependency_overrides[get_project_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/projects",
            json={"code": "PRJ-GET", "name": "Get Project", "location": "Lookup"},
            headers={"Authorization": f"Bearer {token}"},
        )
        created = create_resp.json()
        response = await client.get(f"/api/v1/projects/{created['id']}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["code"] == "PRJ-GET"


@pytest.mark.asyncio
async def test_update_project(token_factory, fake_service):
    app.dependency_overrides[get_project_service] = lambda: fake_service
    token = token_factory(role="INVENTORY_MANAGER")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/projects",
            json={"code": "PRJ-UPDATE", "name": "Old Project", "location": "Old"},
            headers={"Authorization": f"Bearer {token}"},
        )
        project_id = create_resp.json()["id"]
        response = await client.put(
            f"/api/v1/projects/{project_id}",
            json={"name": "New Project", "location": "Updated"},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["name"] == "New Project"


@pytest.mark.asyncio
async def test_delete_project(token_factory, fake_service):
    app.dependency_overrides[get_project_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/projects",
            json={"code": "PRJ-DELETE", "name": "Delete Project", "location": "Remove"},
            headers={"Authorization": f"Bearer {token}"},
        )
        project_id = create_resp.json()["id"]
        response = await client.delete(f"/api/v1/projects/{project_id}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_not_found_project(token_factory, fake_service):
    app.dependency_overrides[get_project_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    missing_id = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/projects/{missing_id}", headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_project_validation(token_factory, fake_service):
    app.dependency_overrides[get_project_service] = lambda: fake_service
    token = token_factory(role="ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/projects",
            json={"code": "", "name": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 422
