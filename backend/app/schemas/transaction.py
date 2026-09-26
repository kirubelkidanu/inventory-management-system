# backend/app/schemas/transaction.py
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TransactionLineCreate(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0, description="Quantity must be strictly positive")
    unit: str = Field(..., min_length=1, max_length=50, description="Unit of measurement")
    remarks: Optional[str] = None


class TransferLineCreate(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0, description="Quantity must be strictly positive")
    unit: str = Field(..., min_length=1, max_length=50, description="Unit of measurement")
    remarks: Optional[str] = None


class GRVCreate(BaseModel):
    warehouse_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    transaction_date: date = Field(default_factory=date.today)
    supplier_name: Optional[str] = Field(None, max_length=255)
    invoice_no: Optional[str] = Field(None, max_length=100)
    received_grv_no: Optional[str] = Field(None, max_length=100)
    store_no: Optional[str] = Field(None, max_length=100)
    remarks: Optional[str] = None
    lines: List[TransactionLineCreate] = Field(..., min_length=1, description="At least one line required")

    @field_validator("lines")
    @classmethod
    def validate_unique_items(cls, lines: List[TransactionLineCreate]) -> List[TransactionLineCreate]:
        item_ids = [line.item_id for line in lines]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate item in transaction lines is not allowed (ADR-006).")
        return lines


class SIVCreate(BaseModel):
    warehouse_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    transaction_date: date = Field(default_factory=date.today)
    requested_from: Optional[str] = Field(None, max_length=255)
    project_dept: Optional[str] = Field(None, max_length=255)
    requested_no: Optional[str] = Field(None, max_length=100)
    siv_no: Optional[str] = Field(None, max_length=100)
    material_summary: Optional[str] = Field(None, max_length=255)
    issued_by_name: Optional[str] = Field(None, max_length=255)
    checked_by_name: Optional[str] = Field(None, max_length=255)
    received_by_name: Optional[str] = Field(None, max_length=255)
    approved_by_name: Optional[str] = Field(None, max_length=255)
    remarks: Optional[str] = None
    lines: List[TransactionLineCreate] = Field(..., min_length=1, description="At least one line required")

    @field_validator("lines")
    @classmethod
    def validate_unique_items(cls, lines: List[TransactionLineCreate]) -> List[TransactionLineCreate]:
        item_ids = [line.item_id for line in lines]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate item in transaction lines is not allowed (ADR-006).")
        return lines


class ISTVCreate(BaseModel):
    source_warehouse_id: uuid.UUID
    destination_warehouse_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    transaction_date: date = Field(default_factory=date.today)
    istv_no: Optional[str] = Field(None, max_length=100)
    plate_no: Optional[str] = Field(None, max_length=100)
    driver_name: Optional[str] = Field(None, max_length=255)
    material_summary: Optional[str] = Field(None, max_length=255)
    remarks: Optional[str] = None
    lines: List[TransactionLineCreate] = Field(..., min_length=1, description="At least one line required")

    @field_validator("lines")
    @classmethod
    def validate_unique_items(cls, lines: List[TransactionLineCreate]) -> List[TransactionLineCreate]:
        item_ids = [line.item_id for line in lines]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate item in transaction lines is not allowed (ADR-006).")
        return lines

    @model_validator(mode="after")
    def validate_different_warehouses(self) -> "ISTVCreate":
        if self.source_warehouse_id == self.destination_warehouse_id:
            raise ValueError("Source warehouse and destination warehouse must be different.")
        return self


class ISTRVLineCreate(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0, description="Quantity must be strictly positive")
    remarks: Optional[str] = None


class ISTRVCreate(BaseModel):
    istv_transaction_id: uuid.UUID
    destination_warehouse_id: uuid.UUID
    transaction_date: date = Field(default_factory=date.today)
    remarks: Optional[str] = None
    lines: List[ISTRVLineCreate] = Field(..., min_length=1, description="At least one line required")

    @field_validator("lines")
    @classmethod
    def validate_unique_items(cls, lines: List[ISTRVLineCreate]) -> List[ISTRVLineCreate]:
        item_ids = [line.item_id for line in lines]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate item in transaction lines is not allowed (ADR-006).")
        return lines


class SRVLineCreate(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0, description="Quantity must be strictly positive")
    unit: str = Field(..., min_length=1, max_length=50, description="Unit of measurement")
    remarks: Optional[str] = None


class SRVCreate(BaseModel):
    reference_siv_id: uuid.UUID
    warehouse_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    transaction_date: date = Field(default_factory=date.today)
    remarks: Optional[str] = None
    lines: List[SRVLineCreate] = Field(..., min_length=1, description="At least one line required")

    @field_validator("lines")
    @classmethod
    def validate_unique_items(cls, lines: List[SRVLineCreate]) -> List[SRVLineCreate]:
        item_ids = [line.item_id for line in lines]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate item in transaction lines is not allowed (ADR-006).")
        return lines


class AdjustmentLineCreate(BaseModel):
    item_id: uuid.UUID
    direction: Literal["IN", "OUT"]
    quantity: Decimal = Field(..., gt=0, description="Quantity must be strictly positive")
    unit: str = Field(..., min_length=1, max_length=50, description="Unit of measurement")
    remarks: Optional[str] = None


class AdjustmentCreate(BaseModel):
    warehouse_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    transaction_date: date = Field(default_factory=date.today)
    adjustment_reason: str = Field(..., min_length=1, description="Mandatory reason for stock adjustment")
    remarks: Optional[str] = None
    lines: List[AdjustmentLineCreate] = Field(..., min_length=1, description="At least one line required")

    @field_validator("adjustment_reason")
    @classmethod
    def validate_non_empty_reason(cls, val: str) -> str:
        if not val or not val.strip():
            raise ValueError("Adjustment reason cannot be empty or whitespace.")
        return val.strip()

    @field_validator("lines")
    @classmethod
    def validate_unique_items(cls, lines: List[AdjustmentLineCreate]) -> List[AdjustmentLineCreate]:
        item_ids = [line.item_id for line in lines]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate item in transaction lines is not allowed (ADR-006).")
        return lines


class TransactionLineRead(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    line_number: int
    item_id: uuid.UUID
    quantity: Decimal
    unit: str
    remarks: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TransactionRead(BaseModel):
    id: uuid.UUID
    transaction_number: str
    transaction_type: str
    status: str
    transaction_date: date
    warehouse_id: Optional[uuid.UUID] = None
    source_warehouse_id: Optional[uuid.UUID] = None
    destination_warehouse_id: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None
    reference_transaction_id: Optional[uuid.UUID] = None
    external_reference: Optional[str] = None
    supplier_name: Optional[str] = None
    invoice_no: Optional[str] = None
    received_grv_no: Optional[str] = None
    store_no: Optional[str] = None
    requested_from: Optional[str] = None
    project_dept: Optional[str] = None
    requested_no: Optional[str] = None
    siv_no: Optional[str] = None
    issued_by_name: Optional[str] = None
    checked_by_name: Optional[str] = None
    received_by_name: Optional[str] = None
    approved_by_name: Optional[str] = None
    istv_no: Optional[str] = None
    plate_no: Optional[str] = None
    driver_name: Optional[str] = None
    material_summary: Optional[str] = None
    adjustment_reason: Optional[str] = None
    remarks: Optional[str] = None
    created_by: uuid.UUID
    created_at: datetime
    posted_by: Optional[uuid.UUID] = None
    posted_at: Optional[datetime] = None
    lines: List[TransactionLineRead] = []

    model_config = ConfigDict(from_attributes=True)


class TransferLineRead(BaseModel):
    id: uuid.UUID
    transfer_record_id: uuid.UUID
    item_id: uuid.UUID
    sent_quantity: Decimal
    received_quantity: Decimal
    remaining_quantity: Decimal

    model_config = ConfigDict(from_attributes=True)


class TransferRecordRead(BaseModel):
    id: uuid.UUID
    istv_transaction_id: uuid.UUID
    source_warehouse_id: uuid.UUID
    destination_warehouse_id: uuid.UUID
    plate_no: Optional[str] = None
    driver_name: Optional[str] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    lines: List[TransferLineRead] = []

    model_config = ConfigDict(from_attributes=True)
