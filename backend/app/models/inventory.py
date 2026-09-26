# backend/app/models/inventory.py
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Numeric, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class InventoryBalance(Base):
    __tablename__ = "inventory_balances"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "item_id", name="uq_inventory_balances_wh_item"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), default=Decimal("0.0000"), nullable=False
    )
    quantity_reserved: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), default=Decimal("0.0000"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    warehouse = relationship("Warehouse")
    item = relationship("Item")