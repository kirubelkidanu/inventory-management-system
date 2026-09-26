from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    item_code: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    category_id: UUID
    default_unit: str = Field(..., min_length=1, max_length=50)
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1)
    category_id: UUID | None = None
    default_unit: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class ItemRead(ItemBase):
    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
