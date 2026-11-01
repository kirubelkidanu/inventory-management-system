from datetime import date, datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, model_validator


class InventoryBalanceBase(BaseModel):
    quantity_on_hand: float
    quantity_reserved: float
    available_quantity: Optional[float] = None

    @model_validator(mode="after")
    def compute_available(self) -> "InventoryBalanceBase":
        if self.available_quantity is None:
            self.available_quantity = float(self.quantity_on_hand) - float(self.quantity_reserved)
        return self


class InventoryBalanceRead(InventoryBalanceBase):
    warehouse_id: uuid.UUID
    item_id: uuid.UUID
    item_code: Optional[str] = None
    item_description: Optional[str] = None
    category_name: Optional[str] = None
    unit: Optional[str] = None
    warehouse_code: Optional[str] = None
    warehouse_name: Optional[str] = None
    warehouse_is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class StockMovementBase(BaseModel):
    transaction_id: uuid.UUID
    transaction_line_id: uuid.UUID
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    movement_type: str
    quantity: float
    signed_quantity: float
    running_balance: Optional[float] = None
    movement_date: date
    created_at: datetime


class StockMovementRead(StockMovementBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class ReconciliationData(BaseModel):
    warehouse_id: uuid.UUID
    warehouse_code: str
    warehouse_name: str
    item_id: uuid.UUID
    item_code: str
    item_description: str
    projected_balance: float
    ledger_cumulative_balance: float
    discrepancy: float
