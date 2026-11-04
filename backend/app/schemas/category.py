from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Category code (e.g. 01, 15, 17)")
    name: str = Field(..., min_length=1, max_length=255, description="Category name (e.g. CEMENT, STATIONERY)")
    description: Optional[str] = Field(default=None, description="Optional description")

    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(CategoryBase):
    is_active: bool = Field(default=True, description="Active status")

    @field_validator("code")
    @classmethod
    def clean_code(cls, v: str) -> str:
        s = v.strip().upper()
        if not s:
            raise ValueError("Category code cannot be blank.")
        return s

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Category name cannot be blank.")
        return s


class CategoryUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("code")
    @classmethod
    def clean_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip().upper()
        if not s:
            raise ValueError("Category code cannot be blank.")
        return s

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("Category name cannot be blank.")
        return s


class CategoryStatusUpdate(BaseModel):
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class CategoryRead(CategoryBase):
    id: UUID
    is_active: bool
    item_count: int = Field(default=0, description="Number of active catalog items in this category")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
