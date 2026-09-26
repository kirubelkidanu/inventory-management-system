"""
SQLAlchemy ORM models for all 14 database tables.

These models mirror the schema defined in docs/DATABASE.md and implemented
in database/migrations/001_initial_schema.sql exactly.
No business logic lives here — models are plain data representations only.

Key invariants:
- inventory_balances and stock_movements are written ONLY through the
  service layer within a database transaction.
- stock_movements rows are NEVER updated or deleted (enforced by DB trigger).
"""
import enum
import uuid
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP

from app.core.database import Base


# ---------------------------------------------------------------------------
# Enums (mirrors CHECK constraints in migration)
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    INVENTORY_MANAGER = "INVENTORY_MANAGER"
    STORE_KEEPER = "STORE_KEEPER"
    VIEWER = "VIEWER"


class TransactionType(str, enum.Enum):
    GRV = "GRV"
    SIV = "SIV"
    ISTV = "ISTV"
    ISTRV = "ISTRV"
    SRV = "SRV"
    ADJUSTMENT = "ADJUSTMENT"


class TransactionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    CANCELLED = "CANCELLED"
    CORRECTED = "CORRECTED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    COMPLETED = "COMPLETED"


class MovementType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"


class TransferStatus(str, enum.Enum):
    IN_TRANSIT = "IN_TRANSIT"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AuditAction(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    POST = "POST"
    CANCEL = "CANCEL"
    CORRECT = "CORRECT"
    IMPORT = "IMPORT"
    DELETE = "DELETE"


class ImportType(str, enum.Enum):
    ITEM_MASTER = "ITEM_MASTER"
    INITIAL_STOCK = "INITIAL_STOCK"
    WAREHOUSES = "WAREHOUSES"
    PROJECTS = "PROJECTS"


class ImportStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PARSED = "PARSED"
    VALIDATED = "VALIDATED"
    IMPORTING = "IMPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# 2.1 users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    auth_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# 2.2 projects
# ---------------------------------------------------------------------------

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# 2.3 warehouses
# ---------------------------------------------------------------------------

class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    default_project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    default_project: Mapped[Project | None] = relationship("Project", lazy="select")


# ---------------------------------------------------------------------------
# 2.4 categories
# ---------------------------------------------------------------------------

class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# 2.5 items
# ---------------------------------------------------------------------------

class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    item_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    default_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    category: Mapped[Category] = relationship("Category", lazy="select")


# ---------------------------------------------------------------------------
# 2.6 inventory_balances
# ---------------------------------------------------------------------------

class InventoryBalance(Base):
    """
    Current-state projection.
    - Used for fast balance reads and stock availability checks.
    - Locked with SELECT ... FOR UPDATE in deterministic (warehouse_id, item_id)
      order before any stock-changing operation.
    - NEVER written directly from the browser or from outside a service transaction.
    """
    __tablename__ = "inventory_balances"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "item_id", name="uq_inventory_balances_wh_item"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), nullable=False, default=Decimal("0.0000")
    )
    quantity_reserved: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), nullable=False, default=Decimal("0.0000")
    )
    updated_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    warehouse: Mapped[Warehouse] = relationship("Warehouse", lazy="select")
    item: Mapped[Item] = relationship("Item", lazy="select")


# ---------------------------------------------------------------------------
# 2.7 transactions (voucher headers)
# ---------------------------------------------------------------------------

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transaction_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    transaction_date: Mapped[Date] = mapped_column(Date, nullable=False)

    # Warehouse associations (nullable; enforced by DB CHECK constraints)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT")
    )
    source_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT")
    )
    destination_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT")
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL")
    )
    reference_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="RESTRICT")
    )
    external_reference: Mapped[str | None] = mapped_column(String(100))

    # Physical GRV voucher fields
    supplier_name: Mapped[str | None] = mapped_column(String(255))
    invoice_no: Mapped[str | None] = mapped_column(String(100))
    received_grv_no: Mapped[str | None] = mapped_column(String(100))
    store_no: Mapped[str | None] = mapped_column(String(100))

    # Physical SIV voucher fields
    requested_from: Mapped[str | None] = mapped_column(String(255))
    project_dept: Mapped[str | None] = mapped_column(String(255))
    requested_no: Mapped[str | None] = mapped_column(String(100))
    siv_no: Mapped[str | None] = mapped_column(String(100))
    issued_by_name: Mapped[str | None] = mapped_column(String(255))
    checked_by_name: Mapped[str | None] = mapped_column(String(255))
    received_by_name: Mapped[str | None] = mapped_column(String(255))
    approved_by_name: Mapped[str | None] = mapped_column(String(255))

    # Physical ISTV voucher fields
    istv_no: Mapped[str | None] = mapped_column(String(100))
    plate_no: Mapped[str | None] = mapped_column(String(100))
    driver_name: Mapped[str | None] = mapped_column(String(255))
    material_summary: Mapped[str | None] = mapped_column(String(255))

    # Adjustment & remarks
    adjustment_reason: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)

    # Lifecycle audit columns
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    posted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    posted_at: Mapped[TIMESTAMP | None] = mapped_column(TIMESTAMP(timezone=True))
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    cancelled_at: Mapped[TIMESTAMP | None] = mapped_column(TIMESTAMP(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["TransactionLine"]] = relationship(
        "TransactionLine", back_populates="transaction", lazy="select"
    )


# ---------------------------------------------------------------------------
# 2.8 transaction_lines
# ---------------------------------------------------------------------------

class TransactionLine(Base):
    __tablename__ = "transaction_lines"
    __table_args__ = (
        UniqueConstraint("transaction_id", "line_number", name="uq_transaction_line_index"),
        UniqueConstraint("transaction_id", "item_id", name="uq_transaction_item"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text)

    transaction: Mapped[Transaction] = relationship(
        "Transaction", back_populates="lines"
    )
    item: Mapped[Item] = relationship("Item", lazy="select")


# ---------------------------------------------------------------------------
# 2.9 stock_movements (IMMUTABLE — never updated or deleted)
# ---------------------------------------------------------------------------

class StockMovement(Base):
    """
    Append-only historical inventory event ledger.
    The DB trigger trg_protect_stock_movements enforces immutability at the
    database level. Application code must never attempt UPDATE or DELETE here.
    """
    __tablename__ = "stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transaction_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transaction_lines.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL")
    )
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    signed_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    running_balance: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    movement_date: Mapped[Date] = mapped_column(Date, nullable=False)
    created_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# 2.10 transfer_records
# ---------------------------------------------------------------------------

class TransferRecord(Base):
    __tablename__ = "transfer_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    istv_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    source_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    destination_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plate_no: Mapped[str | None] = mapped_column(String(100))
    driver_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="IN_TRANSIT"
    )
    created_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[TIMESTAMP | None] = mapped_column(TIMESTAMP(timezone=True))

    lines: Mapped[list["TransferLine"]] = relationship(
        "TransferLine", back_populates="transfer_record", lazy="select"
    )


# ---------------------------------------------------------------------------
# 2.11 transfer_lines
# ---------------------------------------------------------------------------

class TransferLine(Base):
    __tablename__ = "transfer_lines"
    __table_args__ = (
        UniqueConstraint(
            "transfer_record_id", "item_id", name="uq_transfer_lines_record_item"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transfer_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfer_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sent_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), nullable=False, default=Decimal("0.0000")
    )
    # remaining_quantity is GENERATED ALWAYS AS (sent_quantity - received_quantity)
    # in the database; do NOT write to this column from application code.

    transfer_record: Mapped[TransferRecord] = relationship(
        "TransferRecord", back_populates="lines"
    )
    item: Mapped[Item] = relationship("Item", lazy="select")


# ---------------------------------------------------------------------------
# 2.12 audit_logs
# ---------------------------------------------------------------------------

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    before_state: Mapped[dict | None] = mapped_column(JSONB)
    after_state: Mapped[dict | None] = mapped_column(JSONB)
    change_summary: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# 2.13 import_batches
# ---------------------------------------------------------------------------

class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    import_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="UPLOADED"
    )
    staged_data: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[TIMESTAMP | None] = mapped_column(TIMESTAMP(timezone=True))


# ---------------------------------------------------------------------------
# 2.14 import_errors
# ---------------------------------------------------------------------------

class ImportError(Base):
    __tablename__ = "import_errors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    column_name: Mapped[str | None] = mapped_column(String(100))
    raw_value: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
