from app.schemas.transaction import OpeningBalanceCreate, OpeningBalanceLineCreate
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
from app.services.transaction import TransactionService
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
        self.tx_service = TransactionService(session)
        self.tx_service.repo = self.tx_repo

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
        fast_category_lookup: Dict[str, Category] = {}
        for key, cat in categories_map.items():
            if not key:
                continue
            k_upper = key.strip().upper()
            fast_category_lookup[k_upper] = cat
            fast_category_lookup[k_upper.replace(" ", "")] = cat
            if " - " in k_upper:
                for part in k_upper.split(" - "):
                    p = part.strip()
                    if p:
                        fast_category_lookup.setdefault(p, cat)
                        fast_category_lookup.setdefault(p.replace(" ", ""), cat)
            elif "-" in k_upper:
                for part in k_upper.split("-"):
                    p = part.strip()
                    if p:
                        fast_category_lookup.setdefault(p, cat)
                        fast_category_lookup.setdefault(p.replace(" ", ""), cat)

        # Standard category code/prefix mappings from docs/PROJECT_SPEC.md Section 2
        STANDARD_PREFIX_TO_CODE = {
            "01-CM": "01",
            "02-ST": "02",
            "03-QR": "03",
            "04-GL": "04",
            "05-TL": "05",
            "06-WD": "06",
            "07-PC": "07",
            "08-SN": "08",
            "09-EL": "09",
            "10-SF": "10",
            "11-OT": "11",
            "12-FL": "12",
            "13-TB": "13",
            "14-TY": "14",
            "14-SN": "14",
            "14-IZ": "14",
            "14-XL": "14",
            "14-BL": "14",
            "14-ER": "14",
            "14-HT": "14",
            "14-CG": "14",
        }
        for prefix, cat_code in STANDARD_PREFIX_TO_CODE.items():
            if cat_code in fast_category_lookup:
                fast_category_lookup.setdefault(prefix, fast_category_lookup[cat_code])

        candidate_item_codes = list({
            str(data.get("item_code", "")).strip()
            for _, data in raw_rows
            if data.get("item_code") is not None and str(data.get("item_code", "")).strip()
        })
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

            # 1. Corrupt/Draft Row Filter:
            # If a row has an empty description and empty unit (e.g. 07-PC-D0159), treat as empty/draft row and skip without error
            if not description and not default_unit:
                continue

            # 2. Steel UOM Defaulting (docs/PROJECT_SPEC.md Section 18 Note 1):
            # If unit measurement is blank/empty, and item code starts with '02-ST-' or category is 'STEEL', assign default 'PCS'
            if not default_unit:
                cat_upper = category_str.strip().upper()
                main_upper = str(row_data.get("main_category", "")).strip().upper()
                sub_upper = str(row_data.get("sub_category", "")).strip().upper()
                if (
                    item_code.startswith("02-ST-")
                    or cat_upper == "STEEL"
                    or cat_upper.startswith("02-ST")
                    or cat_upper == "02"
                    or main_upper == "STEEL"
                    or sub_upper == "STEEL"
                ):
                    default_unit = "PCS"

            # 3. Validate item_code & Existing Catalog Items (DUPLICATE_CODE vs ALREADY_EXISTS)
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
                # Mark as ALREADY_EXISTS and skip from staged insert list (do not break entire batch)
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="item_code",
                        raw_value=item_code,
                        error_code="ALREADY_EXISTS",
                        error_message=f"Item code already exists in catalog: '{item_code}'. Skipped.",
                        created_at=now_utc,
                    )
                )
                row_has_error = True
                seen_file_item_codes.add(item_code)
            else:
                seen_file_item_codes.add(item_code)

            # 4. Validate description
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

            # 5. Validate category across category_str, sub_category, main_category, and item_code prefix
            matched_category: Optional[Category] = None
            category_candidates = [
                category_str,
                str(row_data.get("sub_category", "")).strip(),
                str(row_data.get("main_category", "")).strip(),
            ]
            if item_code and "-" in item_code:
                parts = item_code.split("-")
                category_candidates.append(parts[0])
                if len(parts) >= 2:
                    category_candidates.append(f"{parts[0]}-{parts[1]}")

            for cat_cand in category_candidates:
                if not cat_cand:
                    continue
                cand_clean = cat_cand.strip().upper()
                matched_category = fast_category_lookup.get(cand_clean) or fast_category_lookup.get(cand_clean.replace(" ", ""))
                if matched_category is not None:
                    break
                if " - " in cand_clean:
                    for part in cand_clean.split(" - "):
                        p = part.strip()
                        matched_category = fast_category_lookup.get(p) or fast_category_lookup.get(p.replace(" ", ""))
                        if matched_category is not None:
                            break
                elif "-" in cand_clean:
                    for part in cand_clean.split("-"):
                        p = part.strip()
                        matched_category = fast_category_lookup.get(p) or fast_category_lookup.get(p.replace(" ", ""))
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

            # 6. Validate default_unit
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

            # If row valid, record staged item (only genuinely new items that pass validation)
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
        fatal_error_rows = len({err.row_number for err in import_errors if err.error_code != "ALREADY_EXISTS"})
        error_rows = len({err.row_number for err in import_errors})
        valid_rows = len(valid_items)

        if fatal_error_rows == 0 and valid_rows > 0:
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
        total_value = sum(
            (
                Decimal(str(r.get("quantity", "0"))) * Decimal(str(r.get("unit_price", "0")))
                for r in staged_rows
            ),
            Decimal("0.0000"),
        )

        return InitialStockBatchPreview(
            batch=ImportBatchRead.model_validate(batch),
            errors=[ImportErrorRead.model_validate(e) for e in errors],
            valid_rows_sample=sample_rows,
            total_value=total_value,
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

        # Check for DB collisions and filter out existing codes to ensure absolute idempotency
        candidate_codes = [item["item_code"] for item in staged_items]
        existing_codes = await self.repo.get_existing_item_codes(candidate_codes)
        items_to_insert = [
            item for item in staged_items if item["item_code"] not in existing_codes
        ]

        now_utc = datetime.now(timezone.utc)
        try:
            # 1. Create items (if any new items remain)
            if items_to_insert:
                items_to_create = [
                    Item(
                        id=uuid.uuid4(),
                        item_code=item["item_code"],
                        description=item["description"],
                        category_id=_to_uuid(item["category_id"]),
                        default_unit=item["default_unit"],
                        is_active=True,
                    )
                    for item in items_to_insert
                ]
                await self.repo.bulk_create_items(items_to_create)
            else:
                items_to_create = []

            # 2. Update batch status to COMPLETED
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
                    "skipped_existing_count": len(existing_codes),
                },
                change_summary=(
                    f"Imported {len(items_to_create)} new items into item master catalog "
                    f"from batch {batch.batch_number} ({len(existing_codes)} existing items skipped)."
                ),
                reason="Item Master Excel Import Commit",
            )

            await self.session.commit()
            return {
                "message": (
                    f"Successfully committed {len(items_to_create)} new items to catalog"
                    f" ({len(existing_codes)} existing items skipped)."
                    if existing_codes
                    else f"Successfully committed {len(items_to_create)} new items to catalog."
                ),
                "batch_id": batch.id,
                "batch_number": batch.batch_number,
                "imported_count": len(items_to_create),
            }
        except Exception:
            await self.session.rollback()
            raise

    # Method alias for backward compatibility with batch naming
    commit_item_master_batch = commit_item_master_import

    async def stage_initial_stock_file(
        self,
        user_id: Any,
        file_name: str,
        file_bytes: bytes,
        warehouse_id: Optional[uuid.UUID] = None,
        project_id: Optional[uuid.UUID] = None,
        transaction_date: Optional[date] = None,
        remarks: Optional[str] = None,
        **kwargs: Any,
    ) -> ImportBatch:
        """
        Parses and stages an Initial Stock spreadsheet (.xlsx or .csv) supporting 4-column sheets.
        Validates:
        - target warehouse existence
        - item exists in catalog (INVALID_ITEM)
        - positive quantity > 0 (INVALID_QUANTITY)
        - UOM defaults to item default_unit; error if mismatched (INVALID_UOM)
        - unit_price defaults to 0.0000; error if negative (INVALID_PRICE)
        - duplicates in file flagged (DUPLICATE_IN_FILE)
        - pre-existing stock balances flagged (ALREADY_EXISTS)
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
        effective_date = transaction_date or date.today()

        # Parse rows
        if lower_name.endswith(".csv"):
            raw_rows = self._parse_initial_stock_csv_rows(file_bytes)
        else:
            raw_rows = self._parse_initial_stock_excel_rows(file_bytes)

        if not raw_rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file contains no data rows.",
            )

        # Target warehouse/project lookup
        target_wh: Optional[Warehouse] = None
        if warehouse_id is not None:
            target_wh = await self.repo.get_warehouse_by_id(warehouse_id)
            if target_wh is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Target warehouse {warehouse_id} not found.",
                )

        target_proj: Optional[Project] = None
        if project_id is not None:
            target_proj = await self.repo.get_project_by_id(project_id)

        # Existing items in warehouse for collision detection
        existing_wh_items: Set[uuid.UUID] = set()
        if target_wh is not None:
            existing_wh_items = await self.repo.get_existing_opening_balance_item_ids(target_wh.id)

        # Extract candidate codes
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

        import_errors: List[ImportError] = []
        valid_rows: List[Dict[str, Any]] = []
        seen_items_in_file: Set[str] = set()
        seen_wh_item_pairs: Set[Tuple[str, str]] = set()

        for row_number, row_data in raw_rows:
            row_has_error = False

            raw_wh_code = row_data.get("warehouse_code")
            wh_code = str(raw_wh_code).strip() if raw_wh_code is not None else ""

            raw_item_code = row_data.get("item_code")
            item_code = str(raw_item_code).strip() if raw_item_code is not None else ""

            raw_quantity = row_data.get("quantity")
            raw_unit = row_data.get("unit")
            unit = str(raw_unit).strip() if raw_unit is not None else ""

            raw_unit_price = row_data.get("unit_price")
            raw_project_code = row_data.get("project_code")
            project_code = str(raw_project_code).strip() if raw_project_code is not None else ""

            raw_remarks = row_data.get("remarks")
            row_remarks = str(raw_remarks).strip() if raw_remarks is not None else remarks

            # Determine Warehouse
            matched_wh: Optional[Warehouse] = None
            if wh_code:
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
            elif target_wh is not None:
                matched_wh = target_wh
                wh_code = target_wh.code
            else:
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="warehouse_code",
                        raw_value=None,
                        error_code="INVALID_WAREHOUSE",
                        error_message="Warehouse is required (specify in file or select target warehouse).",
                        created_at=now_utc,
                    )
                )
                row_has_error = True

            # Determine Item
            matched_item: Optional[Item] = None
            if not item_code:
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="item_code",
                        raw_value=None,
                        error_code="INVALID_ITEM",
                        error_message="Item code (inventory id) is required.",
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

            # In-file duplicate checking
            if item_code and wh_code:
                pair = (wh_code.upper(), item_code.upper())
                if pair in seen_wh_item_pairs:
                    err_code = "DUPLICATE_IN_FILE" if (target_wh is not None and not raw_wh_code) else "DUPLICATE_ENTRY"
                    import_errors.append(
                        ImportError(
                            id=uuid.uuid4(),
                            batch_id=batch_id,
                            row_number=row_number,
                            column_name="item_code",
                            raw_value=item_code,
                            error_code=err_code,
                            error_message=f"Duplicate entry for warehouse '{wh_code}' and item '{item_code}' in file.",
                            created_at=now_utc,
                        )
                    )
                    row_has_error = True
                else:
                    seen_wh_item_pairs.add(pair)

            # Pre-existing balance checking
            if matched_item is not None and matched_wh is not None:
                if matched_item.id in existing_wh_items:
                    import_errors.append(
                        ImportError(
                            id=uuid.uuid4(),
                            batch_id=batch_id,
                            row_number=row_number,
                            column_name="item_code",
                            raw_value=item_code,
                            error_code="ALREADY_EXISTS",
                            error_message=f"Item '{item_code}' already has an initial balance in warehouse '{matched_wh.code}'.",
                            created_at=now_utc,
                        )
                    )
                    row_has_error = True

            # Quantity validation
            parsed_qty: Optional[Decimal] = None
            if raw_quantity is None or str(raw_quantity).strip() == "":
                import_errors.append(
                    ImportError(
                        id=uuid.uuid4(),
                        batch_id=batch_id,
                        row_number=row_number,
                        column_name="quantity",
                        raw_value=None,
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

            # Unit validation & fallback
            if not unit:
                if matched_item is not None:
                    unit = matched_item.default_unit
                else:
                    unit = "PCS"
            elif matched_item is not None and unit.upper() != matched_item.default_unit.upper():
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

            # Unit Price validation & defaulting to 0.0000
            parsed_price = Decimal("0.0000")
            if raw_unit_price is not None and str(raw_unit_price).strip() != "":
                try:
                    parsed_price = Decimal(str(raw_unit_price).strip())
                    if parsed_price < Decimal("0"):
                        import_errors.append(
                            ImportError(
                                id=uuid.uuid4(),
                                batch_id=batch_id,
                                row_number=row_number,
                                column_name="unit_price",
                                raw_value=str(raw_unit_price),
                                error_code="INVALID_PRICE",
                                error_message="Unit price must be non-negative.",
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
                            column_name="unit_price",
                            raw_value=str(raw_unit_price),
                            error_code="INVALID_PRICE",
                            error_message=f"Invalid unit price: '{raw_unit_price}'.",
                            created_at=now_utc,
                        )
                    )
                    row_has_error = True

            # Project
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
            elif target_proj is not None:
                matched_proj = target_proj

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
                        "item_name": matched_item.description,
                        "project_id": str(matched_proj.id) if matched_proj else None,
                        "project_code": matched_proj.code if matched_proj else None,
                        "quantity": str(parsed_qty),
                        "unit": unit,
                        "unit_price": str(raw_unit_price).strip() if (raw_unit_price is not None and str(raw_unit_price).strip()) else str(parsed_price),
                        "total_price": str((parsed_qty * parsed_price).quantize(Decimal("0.0001"))),
                        "remarks": row_remarks,
                    }
                )

        total_rows = len(raw_rows)
        error_rows = len({err.row_number for err in import_errors})
        valid_rows_count = len(valid_rows)

        if error_rows == 0 and valid_rows_count > 0:
            batch_status = "VALIDATED"
        else:
            batch_status = "PARSED"

        total_value = sum(
            (
                Decimal(str(r.get("quantity", "0"))) * Decimal(str(r.get("unit_price", "0")))
                for r in valid_rows
            ),
            Decimal("0.0000"),
        )

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
                staged_data={
                    "rows": valid_rows,
                    "warehouse_id": str(target_wh.id) if target_wh else None,
                    "project_id": str(target_proj.id) if target_proj else None,
                    "transaction_date": str(effective_date),
                    "total_value": str(total_value),
                    "remarks": remarks,
                },
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
        Routes through TransactionService.create_and_post_opening_balance
        to enforce dual-write ledger consistency (ADR-001, ADR-002, ADR-003, ADR-009).
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

        now_utc = datetime.now(timezone.utc)
        today_date = date.today()
        created_transactions: List[Transaction] = []
        self.tx_service.repo = self.tx_repo

        try:
            for wh_uuid, rows in grouped_by_warehouse.items():
                proj_uuid = _to_uuid(rows[0]["project_id"]) if rows[0].get("project_id") else None
                ob_lines = [
                    OpeningBalanceLineCreate(
                        item_id=_to_uuid(r["item_id"]),
                        quantity=Decimal(str(r["quantity"])),
                        unit=r.get("unit"),
                        unit_price=Decimal(str(r.get("unit_price", "0"))),
                        remarks=r.get("remarks"),
                    )
                    for r in rows
                ]
                ob_payload = OpeningBalanceCreate(
                    warehouse_id=wh_uuid,
                    project_id=proj_uuid,
                    transaction_date=today_date,
                    remarks=f"Initial stock import batch {batch.batch_number}",
                    lines=ob_lines,
                )
                tx = await self.tx_service.create_and_post_opening_balance(
                    user_id=parsed_user_id,
                    payload=ob_payload,
                    commit_session=False,
                )
                created_transactions.append(tx)

            batch.status = "COMPLETED"
            batch.completed_at = now_utc
            await self.repo.update_batch(batch)

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
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        try:
            rows: List[Tuple[int, Dict[str, Any]]] = []

            global_row_counter = 1
            for sheet in wb.worksheets:
                sheet_title = sheet.title.strip() if sheet.title else ""
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
        finally:
            wb.close()

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
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        try:
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
        finally:
            wb.close()

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
            elif name in (
                "unit price",
                "unit_price",
                "price",
                "unit cost",
                "unit_cost",
                "cost",
                "rate",
            ):
                mapping["unit_price"] = idx

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
            "unit_price": get_val("unit_price"),
            "project_code": get_val("project_code"),
            "remarks": get_val("remarks"),
        }

    async def list_initial_stock_batches(self) -> List[ImportBatch]:
        """Lists all INITIAL_STOCK import batches ordered by creation date descending."""
        return await self.repo.list_initial_stock_batches()

