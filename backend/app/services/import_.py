# backend/app/services/import_.py
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import io
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from fastapi import HTTPException, status
import openpyxl
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.import_ import ImportBatch, ImportError
from app.models.item import Item
from app.models.project import Project
from app.models.transaction import Transaction, TransactionLine
from app.models.warehouse import Warehouse
from app.repositories.import_ import ImportRepository
from app.repositories.transaction import TransactionRepository
from app.schemas.import_ import (
    ImportBatchPreview,
    ImportBatchRead,
    ImportErrorRead,
    InitialStockBatchPreview,
    InitialStockRow,
)
from app.services.transaction import generate_transaction_number


def _to_uuid(val: Any) -> uuid.UUID:
    """Converts string or UUID into a valid UUID object."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


def generate_batch_number(prefix: str) -> str:
    """Generates a non-colliding batch number: {prefix}-{YYYYMMDD}-{hex}"""
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{date_str}-{suffix}"


class ImportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ImportRepository(session)
        self.tx_repo = TransactionRepository(session)

    async def stage_item_master_file(
        self,
        user_id: Any,
        file_name: str,
        file_bytes: bytes,
    ) -> ImportBatch:
        """
        Parses and stages an Item Master spreadsheet (.xlsx or .csv).
        Validates data row-by-row, recording granular errors in import_errors,
        and saves valid items in staged_data JSONB.
        """
        lower_name = file_name.lower()
        if not (lower_name.endswith(".xlsx") or lower_name.endswith(".csv")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. Only .xlsx and .csv files are supported.",
            )

        parsed_user_id = _to_uuid(user_id)
        batch_id = uuid.uuid4()
        batch_number = generate_batch_number("IMP-ITEM")
        now_utc = datetime.now(timezone.utc)

        # 1. Parse rows from spreadsheet into candidate records
        raw_rows: List[Tuple[int, Dict[str, Any]]] = []
        if lower_name.endswith(".csv"):
            raw_rows = self._parse_csv_rows(file_bytes)
        else:
            raw_rows = self._parse_excel_rows(file_bytes)

        if not raw_rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file contains no data rows.",
            )

        # 2. Pre-fetch categories and existing item codes
        categories_map = await self.repo.get_all_categories()

        candidate_item_codes = [
            str(data.get("item_code", "")).strip()
            for _, data in raw_rows
            if data.get("item_code") is not None and str(data.get("item_code", "")).strip()
        ]
        existing_db_codes = await self.repo.get_existing_item_codes(candidate_item_codes)

        # 3. Row-by-row validation
        seen_file_item_codes: Set[str] = set()
        import_errors: List[ImportError] = []
        valid_items: List[Dict[str, Any]] = []

        for row_number, row_data in raw_rows:
            row_has_error = False

            raw_item_code = row_data.get("item_code")
            item_code = str(raw_item_code).strip() if raw_item_code is not None else ""

            raw_description = row_data.get("description")
            description = (
                str(raw_description).strip() if raw_description is not None else ""
            )

            raw_category = row_data.get("category")
            category_str = (
                str(raw_category).strip() if raw_category is not None else ""
            )

            raw_unit = row_data.get("default_unit")
            default_unit = str(raw_unit).strip() if raw_unit is not None else ""

            # Drop trailing empty draft rows that have no description and no unit (e.g. 07-PC-D0159)
            if not description and not default_unit:
                continue

            # Validate item_code
            if not item_code:
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="item_code",
                        raw_value=str(raw_item_code) if raw_item_code is not None else None,
                        error_code="INVALID_CODE",
                        error_message="Item code is required.",
                        created_at=now_utc,
                    )
                )
                row_has_error = True
            elif item_code in seen_file_item_codes:
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="item_code",
                        raw_value=item_code,
                        error_code="DUPLICATE_CODE",
                        error_message=f"Duplicate item code in file: '{item_code}'.",
                        created_at=now_utc,
                    )
                )
                row_has_error = True
            elif item_code in existing_db_codes:
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="item_code",
                        raw_value=item_code,
                        error_code="DUPLICATE_CODE",
                        error_message=f"Item code already exists in catalog: '{item_code}'.",
                        created_at=now_utc,
                    )
                )
                row_has_error = True
            else:
                seen_file_item_codes.add(item_code)

            # Validate description (catches corrupt draft rows such as 07-PC-D0159)
            if not description:
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="description",
                        raw_value=str(raw_description) if raw_description is not None else None,
                        error_code="MISSING_DESCRIPTION",
                        error_message="Item description is required.",
                        created_at=now_utc,
                    )
                )
                row_has_error = True

            # Validate category across category_str, sub_category, and main_category
            matched_category: Optional[Category] = None
            category_candidates = [
                category_str,
                str(row_data.get("sub_category", "")).strip(),
                str(row_data.get("main_category", "")).strip(),
            ]
            for cat_cand in category_candidates:
                if not cat_cand:
                    continue
                cand_clean = cat_cand.upper()
                matched_category = categories_map.get(cand_clean)
                if matched_category is not None:
                    break
                if " - " in cand_clean:
                    for part in cand_clean.split(" - "):
                        matched_category = categories_map.get(part.strip())
                        if matched_category is not None:
                            break
                if matched_category is not None:
                    break

            if matched_category is None:
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="category",
                        raw_value=category_str if category_str else None,
                        error_code="INVALID_CATEGORY",
                        error_message=f"Category '{category_str}' not found in system.",
                        created_at=now_utc,
                    )
                )
                row_has_error = True

            # Validate default_unit
            if not default_unit:
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="default_unit",
                        raw_value=str(raw_unit) if raw_unit is not None else None,
                        error_code="MISSING_UOM",
                        error_message="Unit of measurement is required.",
                        created_at=now_utc,
                    )
                )
                row_has_error = True

            # If row valid, record staged item
            if not row_has_error and matched_category is not None:
                valid_items.append(
                    {
                        "row_number": row_number,
                        "item_code": item_code,
                        "description": description,
                        "category_id": str(matched_category.id),
                        "category_code": matched_category.code,
                        "default_unit": default_unit,
                    }
                )

        # 4. Determine batch status and counts
        total_rows = len(raw_rows)
        error_rows = len({err.row_number for err in import_errors})
        valid_rows = len(valid_items)

        if error_rows == 0 and valid_rows > 0:
            batch_status = "VALIDATED"
        else:
            batch_status = "PARSED"

        # 5. Persist ImportBatch and ImportErrors
        try:
            batch = ImportBatch(
                id=batch_id,
                batch_number=batch_number,
                import_type="ITEM_MASTER",
                file_name=file_name,
                file_size_bytes=len(file_bytes),
                total_rows=total_rows,
                valid_rows=valid_rows,
                error_rows=error_rows,
                status=batch_status,
                staged_data={"items": valid_items},
                created_by=parsed_user_id,
                created_at=now_utc,
            )
            await self.repo.create_batch(batch)

            if import_errors:
                await self.repo.create_errors(import_errors)

            await self.session.commit()
            return batch
        except Exception:
            await self.session.rollback()
            raise

    async def get_batch_preview(self, batch_id: uuid.UUID) -> ImportBatchPreview:
        """Retrieves an import batch along with errors and sample valid items."""
        batch = await self.repo.get_batch_by_id(batch_id)
        if batch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Import batch {batch_id} not found.",
            )

        errors = await self.repo.get_errors_by_batch_id(batch_id)
        staged_items = (batch.staged_data or {}).get("items", []) or (batch.staged_data or {}).get("rows", [])
        sample_items = staged_items[:50]

        return ImportBatchPreview(
            batch=ImportBatchRead.model_validate(batch),
            errors=[ImportErrorRead.model_validate(e) for e in errors],
            valid_items_sample=sample_items,
        )

    async def get_initial_stock_batch_preview(
        self, batch_id: uuid.UUID
    ) -> InitialStockBatchPreview:
        """Retrieves an initial stock import batch along with errors and sample valid rows."""
        batch = await self.repo.get_batch_by_id(batch_id)
        if batch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Import batch {batch_id} not found.",
            )

        errors = await self.repo.get_errors_by_batch_id(batch_id)
        staged_rows = (batch.staged_data or {}).get("rows", [])
        sample_rows = staged_rows[:50]

        return InitialStockBatchPreview(
            batch=ImportBatchRead.model_validate(batch),
            errors=[ImportErrorRead.model_validate(e) for e in errors],
            valid_rows_sample=sample_rows,
        )

    async def commit_item_master_import(
        self,
        user_id: Any,
        batch_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Atomically commits valid staged items from an import batch into the items catalog.
        Workflow:
        1. Validates batch existence and status (rejects COMPLETED or non-staged).
        2. Validates presence of valid staged items.
        3. Checks for any recent duplicate item codes against the database.
        4. Inserts items in bulk.
        5. Records AuditLog entry.
        6. Updates batch status to COMPLETED and sets completed_at.
        7. Commits atomically in one PostgreSQL transaction.
        """
        parsed_user_id = _to_uuid(user_id)
        batch = await self.repo.get_batch_by_id(batch_id)
        if batch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Import batch {batch_id} not found.",
            )

        if batch.status == "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch has already been committed.",
            )

        if batch.status not in ("VALIDATED", "PARSED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batch status '{batch.status}' cannot be committed.",
            )

        staged_items = (batch.staged_data or {}).get("items", [])
        if not staged_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid items to import in batch.",
            )

        # Check for DB collisions before committing
        candidate_codes = [item["item_code"] for item in staged_items]
        existing_codes = await self.repo.get_existing_item_codes(candidate_codes)
        if existing_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot commit: {len(existing_codes)} item code(s) already exist in catalog "
                    f"(e.g. {list(existing_codes)[:5]})."
                ),
            )

        now_utc = datetime.now(timezone.utc)
        try:
            # 1. Create items
            items_to_create = [
                Item(
                    id=uuid.uuid4(),
                    item_code=item["item_code"],
                    description=item["description"],
                    category_id=_to_uuid(item["category_id"]),
                    default_unit=item["default_unit"],
                    is_active=True,
                )
                for item in staged_items
            ]
            await self.repo.bulk_create_items(items_to_create)

            # 2. Update batch
            batch.status = "COMPLETED"
            batch.completed_at = now_utc
            await self.repo.update_batch(batch)

            # 3. Create AuditLog
            await self.repo.create_audit_log(
                actor_user_id=parsed_user_id,
                action="IMPORT",
                entity_type="items",
                entity_id=str(batch.id),
                before_state=None,
                after_state={
                    "batch_number": batch.batch_number,
                    "imported_count": len(items_to_create),
                },
                change_summary=(
                    f"Imported {len(items_to_create)} items into item master catalog "
                    f"from batch {batch.batch_number}."
                ),
                reason="Item Master Excel Import Commit",
            )

            await self.session.commit()
            return {
                "message": "Item master import completed successfully.",
                "batch_id": batch.id,
                "batch_number": batch.batch_number,
                "imported_count": len(items_to_create),
            }
        except Exception:
            await self.session.rollback()
            raise

    async def stage_initial_stock_file(
        self,
        user_id: Any,
        file_name: str,
        file_bytes: bytes,
    ) -> ImportBatch:
        """
        Parses and stages an Initial Stock spreadsheet (.xlsx or .csv).
        Validates row-by-row:
        - warehouse_code exists in warehouses table (INVALID_WAREHOUSE)
        - item_code exists in items table (INVALID_ITEM)
        - quantity is a positive decimal > 0 (INVALID_QUANTITY)
        - unit matches item default_unit or is non-empty (INVALID_UOM)
        - duplicate (warehouse, item) pairs in file flagged (DUPLICATE_ENTRY)
        - project_code exists if provided (INVALID_PROJECT)
        Records granular errors in import_errors and valid rows in staged_data JSONB.
        """
        lower_name = file_name.lower()
        if not (lower_name.endswith(".xlsx") or lower_name.endswith(".csv")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. Only .xlsx and .csv files are supported.",
            )

        parsed_user_id = _to_uuid(user_id)
        batch_id = uuid.uuid4()
        batch_number = generate_batch_number("IMP-STOCK")
        now_utc = datetime.now(timezone.utc)

        # 1. Parse rows from spreadsheet into candidate records
        raw_rows: List[Tuple[int, Dict[str, Any]]] = []
        if lower_name.endswith(".csv"):
            raw_rows = self._parse_initial_stock_csv_rows(file_bytes)
        else:
            raw_rows = self._parse_initial_stock_excel_rows(file_bytes)

        if not raw_rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file contains no data rows.",
            )

        # 2. Extract candidate codes to pre-fetch warehouses, items, and projects
        candidate_wh_codes = list({
            str(data.get("warehouse_code", "")).strip().upper()
            for _, data in raw_rows
            if data.get("warehouse_code") is not None and str(data.get("warehouse_code", "")).strip()
        })
        candidate_item_codes = list({
            str(data.get("item_code", "")).strip().upper()
            for _, data in raw_rows
            if data.get("item_code") is not None and str(data.get("item_code", "")).strip()
        })
        candidate_proj_codes = list({
            str(data.get("project_code", "")).strip().upper()
            for _, data in raw_rows
            if data.get("project_code") is not None and str(data.get("project_code", "")).strip()
        })

        warehouses_map = await self.repo.get_warehouses_by_codes(candidate_wh_codes)
        items_map = await self.repo.get_items_by_codes(candidate_item_codes)
        projects_map = await self.repo.get_projects_by_codes(candidate_proj_codes)

        # 3. Row-by-row validation
        seen_file_pairs: Set[Tuple[str, str]] = set()
        import_errors: List[ImportError] = []
        valid_rows: List[Dict[str, Any]] = []

        for row_number, row_data in raw_rows:
            row_has_error = False

            raw_wh_code = row_data.get("warehouse_code")
            wh_code = str(raw_wh_code).strip() if raw_wh_code is not None else ""

            raw_item_code = row_data.get("item_code")
            item_code = str(raw_item_code).strip() if raw_item_code is not None else ""

            raw_quantity = row_data.get("quantity")
            raw_unit = row_data.get("unit")
            unit = str(raw_unit).strip() if raw_unit is not None else ""

            raw_project_code = row_data.get("project_code")
            project_code = str(raw_project_code).strip() if raw_project_code is not None else ""

            raw_remarks = row_data.get("remarks")
            remarks = str(raw_remarks).strip() if raw_remarks is not None else None

            # Validate warehouse_code
            matched_wh: Optional[Warehouse] = None
            if not wh_code:
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="warehouse_code",
                        raw_value=str(raw_wh_code) if raw_wh_code is not None else None,
                        error_code="INVALID_WAREHOUSE",
                        error_message="Warehouse code is required.",
                        created_at=now_utc,
                    )
                )
                row_has_error = True
            else:
                matched_wh = warehouses_map.get(wh_code.upper())
                if matched_wh is None:
                    import_errors.append(
                        ImportError(
                            id=uuid.uuid4(),
                            batch_id=batch_id,
                            row_number=row_number,
                            column_name="warehouse_code",
                            raw_value=wh_code,
                            error_code="INVALID_WAREHOUSE",
                            error_message=f"Warehouse '{wh_code}' not found in system.",
                            created_at=now_utc,
                        )
                    )
                    row_has_error = True

            # Validate item_code
            matched_item: Optional[Item] = None
            if not item_code:
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="item_code",
                        raw_value=str(raw_item_code) if raw_item_code is not None else None,
                        error_code="INVALID_ITEM",
                        error_message="Item code is required.",
                        created_at=now_utc,
                    )
                )
                row_has_error = True
            else:
                matched_item = items_map.get(item_code.upper())
                if matched_item is None:
                    import_errors.append(
                        ImportError(
                            id=uuid.uuid4(),
                            batch_id=batch_id,
                            row_number=row_number,
                            column_name="item_code",
                            raw_value=item_code,
                            error_code="INVALID_ITEM",
                            error_message=f"Item '{item_code}' not found in catalog.",
                            created_at=now_utc,
                        )
                    )
                    row_has_error = True

            # Validate duplicate (warehouse, item) pairs in file
            if wh_code and item_code:
                pair = (wh_code.upper(), item_code.upper())
                if pair in seen_file_pairs:
                    import_errors.append(
                        ImportError(
                            id=uuid.uuid4(),
                            batch_id=batch_id,
                            row_number=row_number,
                            column_name="item_code",
                            raw_value=item_code,
                            error_code="DUPLICATE_ENTRY",
                            error_message=f"Duplicate entry for warehouse '{wh_code}' and item '{item_code}' in file.",
                            created_at=now_utc,
                        )
                    )
                    row_has_error = True
                else:
                    seen_file_pairs.add(pair)

            # Validate quantity
            parsed_qty: Optional[Decimal] = None
            if raw_quantity is None or str(raw_quantity).strip() == "":
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="quantity",
                        raw_value=str(raw_quantity) if raw_quantity is not None else None,
                        error_code="INVALID_QUANTITY",
                        error_message="Quantity is required.",
                        created_at=now_utc,
                    )
                )
                row_has_error = True
            else:
                try:
                    parsed_qty = Decimal(str(raw_quantity).strip())
                    if parsed_qty <= Decimal("0"):
                        import_errors.append(
                            ImportError(
                                id=uuid.uuid4(),
                                batch_id=batch_id,
                                row_number=row_number,
                                column_name="quantity",
                                raw_value=str(raw_quantity),
                                error_code="INVALID_QUANTITY",
                                error_message=f"Quantity must be greater than zero. Received: {parsed_qty}.",
                                created_at=now_utc,
                            )
                        )
                        row_has_error = True
                except Exception:
                    import_errors.append(
                        ImportError(
                            id=uuid.uuid4(),
                            batch_id=batch_id,
                            row_number=row_number,
                            column_name="quantity",
                            raw_value=str(raw_quantity),
                            error_code="INVALID_QUANTITY",
                            error_message=f"Invalid numeric quantity: '{raw_quantity}'.",
                            created_at=now_utc,
                        )
                    )
                    row_has_error = True

            # Validate unit
            if not unit:
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="unit",
                        raw_value=str(raw_unit) if raw_unit is not None else None,
                        error_code="INVALID_UOM",
                        error_message="Unit of measurement is required.",
                        created_at=now_utc,
                    )
                )
                row_has_error = True
            elif matched_item is not None:
                if unit.upper() != matched_item.default_unit.upper():
                    import_errors.append(
                        ImportError(
                            id=uuid.uuid4(),
                            batch_id=batch_id,
                            row_number=row_number,
                            column_name="unit",
                            raw_value=unit,
                            error_code="INVALID_UOM",
                            error_message=f"Unit '{unit}' does not match item default unit '{matched_item.default_unit}'.",
                            created_at=now_utc,
                        )
                    )
                    row_has_error = True

            # Validate optional project_code
            matched_proj: Optional[Project] = None
            if project_code:
                matched_proj = projects_map.get(project_code.upper())
                if matched_proj is None:
                    import_errors.append(
                        ImportError(
                            id=uuid.uuid4(),
                            batch_id=batch_id,
                            row_number=row_number,
                            column_name="project_code",
                            raw_value=project_code,
                            error_code="INVALID_PROJECT",
                            error_message=f"Project '{project_code}' not found in system.",
                            created_at=now_utc,
                        )
                    )
                    row_has_error = True

            if (
                not row_has_error
                and matched_wh is not None
                and matched_item is not None
                and parsed_qty is not None
            ):
                valid_rows.append(
                    {
                        "row_number": row_number,
                        "warehouse_id": str(matched_wh.id),
                        "warehouse_code": matched_wh.code,
                        "warehouse_name": matched_wh.name,
                        "item_id": str(matched_item.id),
                        "item_code": matched_item.item_code,
                        "item_description": matched_item.description,
                        "project_id": str(matched_proj.id) if matched_proj else None,
                        "project_code": matched_proj.code if matched_proj else None,
                        "quantity": str(parsed_qty),
                        "unit": unit,
                        "remarks": remarks,
                    }
                )

        # 4. Determine batch status and counts
        total_rows = len(raw_rows)
        error_rows = len({err.row_number for err in import_errors})
        valid_rows_count = len(valid_rows)

        if error_rows == 0 and valid_rows_count > 0:
            batch_status = "VALIDATED"
        else:
            batch_status = "PARSED"

        # 5. Persist ImportBatch and ImportErrors
        try:
            batch = ImportBatch(
                id=batch_id,
                batch_number=batch_number,
                import_type="INITIAL_STOCK",
                file_name=file_name,
                file_size_bytes=len(file_bytes),
                total_rows=total_rows,
                valid_rows=valid_rows_count,
                error_rows=error_rows,
                status=batch_status,
                staged_data={"rows": valid_rows},
                created_by=parsed_user_id,
                created_at=now_utc,
            )
            await self.repo.create_batch(batch)

            if import_errors:
                await self.repo.create_errors(import_errors)

            await self.session.commit()
            return batch
        except Exception:
            await self.session.rollback()
            raise

    async def commit_initial_stock_import(
        self,
        user_id: Any,
        batch_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Atomically commits valid staged initial stock from an import batch.
        Workflow:
        1. Validates batch existence and status (rejects COMPLETED or non-staged).
        2. Validates presence of valid staged rows.
        3. Groups staged rows by warehouse_id.
        4. For each warehouse:
           - Generates GRV transaction header (status='POSTED', remarks=f'Initial stock import batch {batch.batch_number}').
           - Acquires deterministic row locks on inventory_balances.
           - Creates transaction lines.
           - Increments inventory_balances.quantity_on_hand.
           - Appends immutable stock_movements (movement_type='IN', signed_quantity=+quantity).
           - Records audit log entry.
        5. Updates batch status to COMPLETED and sets completed_at.
        6. Records audit log for batch commit.
        7. Commits all writes atomically in one PostgreSQL transaction.
        """
        parsed_user_id = _to_uuid(user_id)
        batch = await self.repo.get_batch_by_id(batch_id)
        if batch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Import batch {batch_id} not found.",
            )

        if batch.import_type != "INITIAL_STOCK":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batch import type is '{batch.import_type}', expected 'INITIAL_STOCK'.",
            )

        if batch.status == "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch has already been committed.",
            )

        if batch.status not in ("VALIDATED", "PARSED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batch status '{batch.status}' cannot be committed.",
            )

        staged_rows = (batch.staged_data or {}).get("rows", [])
        if not staged_rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid initial stock rows to import in batch.",
            )

        # Group by warehouse_id
        grouped_by_warehouse: Dict[uuid.UUID, List[Dict[str, Any]]] = {}
        for r in staged_rows:
            wh_uuid = _to_uuid(r["warehouse_id"])
            grouped_by_warehouse.setdefault(wh_uuid, []).append(r)

        tx_repo = self.tx_repo
        now_utc = datetime.now(timezone.utc)
        today_date = date.today()
        created_transactions: List[Transaction] = []

        try:
            for warehouse_id, rows in grouped_by_warehouse.items():
                tx_id = uuid.uuid4()
                tx_number = generate_transaction_number("GRV", today_date)

                # Determine project_id if consistent across rows, or default None
                proj_ids = {r.get("project_id") for r in rows if r.get("project_id")}
                header_project_id = _to_uuid(list(proj_ids)[0]) if len(proj_ids) == 1 else None

                # 1. Create Transaction header
                transaction = Transaction(
                    id=tx_id,
                    transaction_number=tx_number,
                    transaction_type="GRV",
                    status="POSTED",
                    transaction_date=today_date,
                    warehouse_id=warehouse_id,
                    project_id=header_project_id,
                    supplier_name="INITIAL STOCK OPENING",
                    received_grv_no=batch.batch_number,
                    remarks=f"Initial stock import batch {batch.batch_number}",
                    created_by=parsed_user_id,
                    created_at=now_utc,
                    posted_by=parsed_user_id,
                    posted_at=now_utc,
                )
                await tx_repo.create_transaction(transaction)

                # 2. Lock inventory balances deterministically
                item_ids = [_to_uuid(r["item_id"]) for r in rows]
                locked_balances = await tx_repo.lock_inventory_balances_for_update(
                    warehouse_id=warehouse_id,
                    item_ids=item_ids,
                )

                # 3. Create Transaction lines
                lines: List[TransactionLine] = []
                for idx, r in enumerate(rows, start=1):
                    line = TransactionLine(
                        id=uuid.uuid4(),
                        transaction_id=tx_id,
                        line_number=idx,
                        item_id=_to_uuid(r["item_id"]),
                        quantity=Decimal(str(r["quantity"])),
                        unit=r["unit"],
                        remarks=r.get("remarks"),
                    )
                    lines.append(line)
                await tx_repo.create_transaction_lines(lines)

                # 4. Update balances and append stock movements
                for idx, line in enumerate(lines):
                    r = rows[idx]
                    line_proj_id = _to_uuid(r["project_id"]) if r.get("project_id") else header_project_id

                    balance = await tx_repo.get_or_create_balance(
                        warehouse_id=warehouse_id,
                        item_id=line.item_id,
                        existing_balances=locked_balances,
                    )
                    balance.quantity_on_hand += line.quantity
                    balance.updated_at = now_utc
                    running_bal = balance.quantity_on_hand

                    await tx_repo.create_stock_movement(
                        transaction_id=tx_id,
                        transaction_line_id=line.id,
                        item_id=line.item_id,
                        warehouse_id=warehouse_id,
                        project_id=line_proj_id,
                        movement_type="IN",
                        quantity=line.quantity,
                        running_balance=running_bal,
                        movement_date=today_date,
                    )

                # 5. Record AuditLog for this warehouse GRV
                await tx_repo.create_audit_log(
                    actor_user_id=parsed_user_id,
                    action="IMPORT",
                    entity_type="initial_stock",
                    entity_id=str(tx_id),
                    before_state=None,
                    after_state={
                        "transaction_number": tx_number,
                        "transaction_type": "GRV",
                        "status": "POSTED",
                        "warehouse_id": str(warehouse_id),
                        "lines_count": len(lines),
                        "total_quantity": str(sum(l.quantity for l in lines)),
                    },
                    change_summary=(
                        f"Imported initial stock opening balance for warehouse {warehouse_id} "
                        f"({len(lines)} item lines) via batch {batch.batch_number}."
                    ),
                    reason=f"Initial stock import batch {batch.batch_number}",
                )
                created_transactions.append(transaction)

            # 6. Update batch status
            batch.status = "COMPLETED"
            batch.completed_at = now_utc
            await self.repo.update_batch(batch)

            # 7. AuditLog for batch completion
            await self.repo.create_audit_log(
                actor_user_id=parsed_user_id,
                action="IMPORT",
                entity_type="import_batch",
                entity_id=str(batch.id),
                before_state=None,
                after_state={
                    "batch_number": batch.batch_number,
                    "import_type": "INITIAL_STOCK",
                    "status": "COMPLETED",
                    "warehouses_count": len(grouped_by_warehouse),
                    "total_rows_imported": len(staged_rows),
                },
                change_summary=(
                    f"Committed initial stock batch {batch.batch_number} "
                    f"across {len(grouped_by_warehouse)} warehouse(s)."
                ),
                reason="Initial Stock Excel Import Commit",
            )

            await self.session.commit()
            return {
                "message": "Initial stock import completed successfully.",
                "batch_id": batch.id,
                "batch_number": batch.batch_number,
                "imported_rows": len(staged_rows),
                "warehouses_affected": len(grouped_by_warehouse),
                "transactions_created": len(created_transactions),
                "transaction_numbers": [t.transaction_number for t in created_transactions],
            }
        except Exception:
            await self.session.rollback()
            raise

    # -----------------------------------------------------------------------
    # Internal Spreadsheet Row Parsers
    # -----------------------------------------------------------------------

    def _parse_csv_rows(self, file_bytes: bytes) -> List[Tuple[int, Dict[str, Any]]]:
        """Parses rows from CSV bytes, returning (row_number, row_dict)."""
        text = file_bytes.decode("utf-8-sig", errors="replace")
        stream = io.StringIO(text)
        reader = csv.reader(stream)

        header_map: Dict[str, int] = {}
        rows: List[Tuple[int, Dict[str, Any]]] = []

        for idx, row in enumerate(reader, start=1):
            if not row or not any(str(c).strip() for c in row):
                continue
            if not header_map:
                header_map = self._detect_headers(row)
                continue

            row_data = self._extract_row_data(row, header_map)
            rows.append((idx, row_data))

        return rows

    def _parse_excel_rows(self, file_bytes: bytes) -> List[Tuple[int, Dict[str, Any]]]:
        """Parses rows across all worksheets in an Excel workbook."""
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        rows: List[Tuple[int, Dict[str, Any]]] = []

        global_row_counter = 1
        for sheet in wb.worksheets:
            sheet_title = sheet.title.strip()
            header_map: Dict[str, int] = {}

            for row_cells in sheet.iter_rows(values_only=True):
                global_row_counter += 1
                if not row_cells or not any(c is not None and str(c).strip() for c in row_cells):
                    continue

                if not header_map:
                    header_map = self._detect_headers([str(c) if c is not None else "" for c in row_cells])
                    continue

                row_data = self._extract_row_data(row_cells, header_map)
                # If category column missing or blank in row, fall back to sheet name
                if not row_data.get("category"):
                    row_data["category"] = sheet_title

                rows.append((global_row_counter, row_data))

        return rows

    def _detect_headers(self, header_cells: List[Any]) -> Dict[str, int]:
        """Maps canonical field names to column indices based on header names."""
        mapping: Dict[str, int] = {}
        for idx, raw in enumerate(header_cells):
            if raw is None:
                continue
            name = str(raw).strip().lower()
            if name in (
                "inventory id",
                "inventory_id",
                "item_code",
                "item code",
                "code",
                "item id",
                "item_id",
            ):
                mapping["item_code"] = idx
            elif name in (
                "description",
                "descrption",
                "item description",
                "item_description",
                "name",
            ):
                mapping["description"] = idx
            elif name in (
                "main catagories",
                "main categories",
                "major category",
            ):
                mapping["main_category"] = idx
                if "category" not in mapping:
                    mapping["category"] = idx
            elif name in (
                "sub gatagory code",
                "sub category",
                "subcategory",
            ):
                mapping["sub_category"] = idx
                if "category" not in mapping:
                    mapping["category"] = idx
            elif name in (
                "category",
                "category_code",
                "category code",
            ):
                mapping["category"] = idx
            elif name in (
                "unit measurment",
                "unit measurement",
                "unit",
                "default_unit",
                "uom",
            ):
                mapping["default_unit"] = idx

        return mapping

    def _extract_row_data(
        self,
        row_cells: Tuple[Any, ...] | List[Any],
        header_map: Dict[str, int],
    ) -> Dict[str, Any]:
        """Extracts field values using detected column indices."""
        def get_val(key: str) -> Optional[str]:
            if key in header_map and header_map[key] < len(row_cells):
                cell = row_cells[header_map[key]]
                if cell is not None:
                    s = str(cell).strip()
                    return s if s else None
            return None

        return {
            "item_code": get_val("item_code"),
            "description": get_val("description"),
            "category": get_val("category") or get_val("sub_category") or get_val("main_category"),
            "main_category": get_val("main_category"),
            "sub_category": get_val("sub_category"),
            "default_unit": get_val("default_unit"),
        }

    def _parse_initial_stock_csv_rows(
        self, file_bytes: bytes
    ) -> List[Tuple[int, Dict[str, Any]]]:
        """Parses initial stock rows from CSV bytes, returning (row_number, row_dict)."""
        text = file_bytes.decode("utf-8-sig", errors="replace")
        stream = io.StringIO(text)
        reader = csv.reader(stream)

        header_map: Dict[str, int] = {}
        rows: List[Tuple[int, Dict[str, Any]]] = []

        for idx, row in enumerate(reader, start=1):
            if not row or not any(str(c).strip() for c in row):
                continue
            if not header_map:
                header_map = self._detect_initial_stock_headers(row)
                continue

            row_data = self._extract_initial_stock_row_data(row, header_map)
            rows.append((idx, row_data))

        return rows

    def _parse_initial_stock_excel_rows(
        self, file_bytes: bytes
    ) -> List[Tuple[int, Dict[str, Any]]]:
        """Parses initial stock rows across worksheets in an Excel workbook."""
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        rows: List[Tuple[int, Dict[str, Any]]] = []

        global_row_counter = 1
        for sheet in wb.worksheets:
            header_map: Dict[str, int] = {}

            for row_cells in sheet.iter_rows(values_only=True):
                global_row_counter += 1
                if not row_cells or not any(
                    c is not None and str(c).strip() for c in row_cells
                ):
                    continue

                if not header_map:
                    header_map = self._detect_initial_stock_headers(
                        [str(c) if c is not None else "" for c in row_cells]
                    )
                    continue

                row_data = self._extract_initial_stock_row_data(row_cells, header_map)
                rows.append((global_row_counter, row_data))

        return rows

    def _detect_initial_stock_headers(
        self, header_cells: List[Any]
    ) -> Dict[str, int]:
        """Maps canonical initial stock field names to column indices."""
        mapping: Dict[str, int] = {}
        for idx, raw in enumerate(header_cells):
            if raw is None:
                continue
            name = str(raw).strip().lower()
            if name in (
                "warehouse_code",
                "warehouse code",
                "warehouse",
                "store_code",
                "store code",
                "store",
                "wh_code",
                "wh",
            ):
                mapping["warehouse_code"] = idx
            elif name in (
                "item_code",
                "item code",
                "code",
                "inventory id",
                "inventory_id",
                "item id",
                "item_id",
            ):
                mapping["item_code"] = idx
            elif name in (
                "quantity",
                "qty",
                "opening_balance",
                "opening balance",
                "opening_qty",
                "count",
                "balance",
                "opening stock",
            ):
                mapping["quantity"] = idx
            elif name in (
                "unit",
                "unit measurment",
                "unit measurement",
                "default_unit",
                "uom",
                "unit of measure",
            ):
                mapping["unit"] = idx
            elif name in (
                "project_code",
                "project code",
                "project",
                "proj_code",
            ):
                mapping["project_code"] = idx
            elif name in (
                "remarks",
                "remark",
                "notes",
                "note",
                "comment",
                "description",
            ):
                mapping["remarks"] = idx

        return mapping

    def _extract_initial_stock_row_data(
        self,
        row_cells: Tuple[Any, ...] | List[Any],
        header_map: Dict[str, int],
    ) -> Dict[str, Any]:
        """Extracts initial stock field values using detected column indices."""
        def get_val(key: str) -> Optional[str]:
            if key in header_map and header_map[key] < len(row_cells):
                cell = row_cells[header_map[key]]
                if cell is not None:
                    s = str(cell).strip()
                    return s if s else None
            return None

        return {
            "warehouse_code": get_val("warehouse_code"),
            "item_code": get_val("item_code"),
            "quantity": get_val("quantity"),
            "unit": get_val("unit"),
            "project_code": get_val("project_code"),
            "remarks": get_val("remarks"),
        }
