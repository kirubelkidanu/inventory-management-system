# backend/app/schemas/report.py
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict


class TrialBalanceItem(BaseModel):
    movement_id: uuid.UUID
    movement_date: date
    created_at: datetime
    transaction_id: uuid.UUID
    transaction_number: str
    transaction_type: str
    reference_number: Optional[str] = None
    item_id: uuid.UUID
    item_code: str
    item_description: str
    category_name: str
    unit: str
    warehouse_id: uuid.UUID
    warehouse_code: str
    warehouse_name: str
    project_name: Optional[str] = None
    plate_no: Optional[str] = None
    driver_name: Optional[str] = None
    in_quantity: Decimal
    out_quantity: Decimal
    signed_quantity: Decimal
    running_balance: Optional[Decimal] = None
    status: str
    entered_by_name: str

    model_config = ConfigDict(from_attributes=True)


class TrialBalanceResponse(BaseModel):
    total_count: int
    page: int
    page_size: int
    items: List[TrialBalanceItem]
    total_in: Decimal
    total_out: Decimal

    model_config = ConfigDict(from_attributes=True)


class StockBalanceItem(BaseModel):
    warehouse_id: uuid.UUID
    warehouse_code: str
    warehouse_name: str
    project_name: Optional[str] = None
    category_name: str
    item_id: uuid.UUID
    item_code: str
    item_description: str
    unit: str
    quantity_on_hand: Decimal
    quantity_reserved: Decimal
    quantity_available: Decimal

    model_config = ConfigDict(from_attributes=True)


class StockBalanceResponse(BaseModel):
    total_count: int
    items: List[StockBalanceItem]

    model_config = ConfigDict(from_attributes=True)


class InTransitReportItem(BaseModel):
    transfer_record_id: uuid.UUID
    istv_transaction_id: uuid.UUID
    istv_number: str
    transaction_date: date
    source_warehouse_name: str
    destination_warehouse_name: str
    plate_no: Optional[str] = None
    driver_name: Optional[str] = None
    status: str
    item_id: uuid.UUID
    item_code: str
    item_description: str
    unit: str
    sent_quantity: Decimal
    received_quantity: Decimal
    remaining_quantity: Decimal

    model_config = ConfigDict(from_attributes=True)
