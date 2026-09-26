# backend/app/schemas/reconciliation.py
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PhysicalCountItemInput(BaseModel):
    item_id: uuid.UUID
    counted_quantity: Decimal = Field(..., ge=Decimal("0"), description="Counted quantity must be >= 0")
    remarks: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PhysicalCountSubmitRequest(BaseModel):
    warehouse_id: uuid.UUID
    count_date: date = Field(default_factory=date.today)
    count_reference: str = Field(..., min_length=1, description="Count batch reference e.g. Q3-2026-COUNT-WH001")
    remarks: Optional[str] = None
    counts: List[PhysicalCountItemInput] = Field(..., min_length=1, description="At least one counted item required")

    @field_validator("counts")
    @classmethod
    def validate_unique_items(cls, counts: List[PhysicalCountItemInput]) -> List[PhysicalCountItemInput]:
        item_ids = [c.item_id for c in counts]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate item in count lines is not allowed.")
        return counts

    model_config = ConfigDict(from_attributes=True)


class VarianceItem(BaseModel):
    item_id: uuid.UUID
    item_code: str
    item_description: str
    unit: str
    system_quantity: Decimal
    counted_quantity: Decimal
    variance_quantity: Decimal  # counted - system
    adjustment_direction: Literal["IN", "OUT", "NONE"]
    remarks: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReconciliationPreviewResponse(BaseModel):
    warehouse_id: uuid.UUID
    warehouse_code: str
    warehouse_name: str
    count_date: date
    count_reference: str
    total_items_counted: int
    matched_items_count: int
    surplus_items_count: int
    deficit_items_count: int
    variances: List[VarianceItem]

    model_config = ConfigDict(from_attributes=True)


class ReconciliationCommitRequest(BaseModel):
    warehouse_id: uuid.UUID
    count_date: date = Field(default_factory=date.today)
    count_reference: str = Field(..., min_length=1, description="Count batch reference e.g. Q3-2026-COUNT-WH001")
    adjustment_reason: str = Field(..., min_length=1, description="Mandatory reason for stock adjustment")
    counts: List[PhysicalCountItemInput] = Field(..., min_length=1, description="At least one counted item required")

    @field_validator("adjustment_reason")
    @classmethod
    def validate_non_empty_reason(cls, val: str) -> str:
        if not val or not val.strip():
            raise ValueError("Adjustment reason cannot be empty or whitespace.")
        return val.strip()

    @field_validator("counts")
    @classmethod
    def validate_unique_items(cls, counts: List[PhysicalCountItemInput]) -> List[PhysicalCountItemInput]:
        item_ids = [c.item_id for c in counts]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate item in count lines is not allowed.")
        return counts

    model_config = ConfigDict(from_attributes=True)


class CountSheetItem(BaseModel):
    item_id: uuid.UUID
    item_code: str
    item_description: str
    category_name: str
    unit: str
    system_quantity_on_hand: Decimal

    model_config = ConfigDict(from_attributes=True)


class CountSheetResponse(BaseModel):
    warehouse_id: uuid.UUID
    warehouse_code: str
    warehouse_name: str
    generated_at: datetime
    total_items: int
    items: List[CountSheetItem]

    model_config = ConfigDict(from_attributes=True)
