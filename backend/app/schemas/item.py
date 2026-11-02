from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ItemBase(BaseModel):
    item_code: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    category_id: UUID
    default_unit: str = Field(..., min_length=1, max_length=50)
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)

    @field_validator("item_code", "description", "default_unit")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1)
    category_id: UUID | None = None
    default_unit: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("description", "default_unit")
    @classmethod
    def validate_optional_strings(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Field cannot be empty or whitespace.")
            return s
        return v


class ItemRead(ItemBase):
    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ItemDeleteResult(BaseModel):
    id: UUID
    item_code: str
    outcome: str  # "DELETED" | "ARCHIVED"
    message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ItemBulkDeleteRequest(BaseModel):
    item_ids: list[UUID] = Field(..., min_length=1)


class ItemBulkDeleteResult(BaseModel):
    deleted_count: int
    archived_count: int
    results: list[ItemDeleteResult]

    model_config = ConfigDict(from_attributes=True)
