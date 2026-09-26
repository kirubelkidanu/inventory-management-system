# backend/app/schemas/import_.py
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ImportBatchRead(BaseModel):
    id: uuid.UUID
    batch_number: str
    import_type: str
    file_name: str
    file_size_bytes: int
    total_rows: int
    valid_rows: int
    error_rows: int
    status: str
    staged_data: Optional[Dict[str, Any]] = None
    created_by: uuid.UUID
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ImportErrorRead(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    row_number: int
    column_name: Optional[str] = None
    raw_value: Optional[str] = None
    error_code: str
    error_message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportBatchPreview(BaseModel):
    batch: ImportBatchRead
    errors: List[ImportErrorRead] = []
    valid_items_sample: List[Dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)


class InitialStockRow(BaseModel):
    warehouse_code: str
    item_code: str
    quantity: Decimal = Field(..., gt=Decimal("0"))
    unit: str
    project_code: Optional[str] = None
    remarks: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InitialStockBatchPreview(BaseModel):
    batch: ImportBatchRead
    errors: List[ImportErrorRead] = []
    valid_rows_sample: List[Dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)
