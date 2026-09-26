from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    location: str | None = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = None
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class ProjectRead(ProjectBase):
    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
