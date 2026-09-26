# backend/app/models/transaction.py
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Text, Date, DateTime, Numeric, Integer, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transaction_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, server_default=func.current_date(), nullable=False)
    
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=True)
    source_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=True)
    destination_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    reference_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=True)
    
    external_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    received_grv_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    store_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    requested_from: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_dept: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    siv_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issued_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checked_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    received_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    istv_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    plate_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    driver_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    material_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    adjustment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    posted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines = relationship("TransactionLine", back_populates="transaction", lazy="selectin")


class TransactionLine(Base):
    __tablename__ = "transaction_lines"
    __table_args__ = (
        UniqueConstraint("transaction_id", "line_number"),
        UniqueConstraint("transaction_id", "item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    transaction = relationship("Transaction", back_populates="lines")
    item = relationship("Item")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False)
    transaction_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transaction_lines.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    signed_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    running_balance: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    transaction = relationship("Transaction")
    transaction_line = relationship("TransactionLine")


class TransferRecord(Base):
    __tablename__ = "transfer_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    istv_transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"), unique=True, nullable=False)
    source_warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    destination_warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    plate_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    driver_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="IN_TRANSIT", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines = relationship("TransferLine", back_populates="transfer_record")


class TransferLine(Base):
    __tablename__ = "transfer_lines"
    __table_args__ = (
        UniqueConstraint("transfer_record_id", "item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transfer_record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transfer_records.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    sent_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=Decimal("0.0000"), nullable=False)

    transfer_record = relationship("TransferRecord", back_populates="lines")

    @property
    def remaining_quantity(self) -> Decimal:
        return self.sent_quantity - self.received_quantity