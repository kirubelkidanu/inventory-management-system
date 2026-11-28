# backend/app/services/report.py
from datetime import date, datetime, timezone
from decimal import Decimal
import io
from typing import Any, Dict, List, Optional
import uuid

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.report import ReportRepository
from app.schemas.report import (
    InTransitReportItem,
    RemainingStockSummaryItem,
    StockBalanceItem,
    StockBalanceResponse,
    TrialBalanceItem,
    TrialBalanceResponse,
)


class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ReportRepository(session)

    def _resolve_reference_number(self, row: Dict[str, Any]) -> Optional[str]:
        """Extracts the best document reference based on available transaction fields."""
        return (
            row.get("invoice_no")
            or row.get("siv_no")
            or row.get("istv_no")
            or row.get("istrv_no")
            or row.get("received_grv_no")
            or row.get("requested_no")
            or row.get("external_reference")
            or row.get("adjustment_reason")
        )

    def _compute_wac_and_summary(
        self, all_rows: List[Dict[str, Any]]
    ) -> tuple[
        Dict[uuid.UUID, tuple[Optional[Decimal], Optional[Decimal]]],
        List[RemainingStockSummaryItem],
        Decimal,
        Decimal,
    ]:
        """
        Computes chronological Moving Weighted Average Cost (WAC) per (warehouse_id, item_id)
        using exact Decimal arithmetic, plus the deduplicated RemainingStockSummaryItem list.
        """
        groups: Dict[tuple[Any, Any], List[Dict[str, Any]]] = {}
        for row in all_rows:
            key = (row["warehouse_id"], row["item_id"])
            groups.setdefault(key, []).append(row)

        per_movement: Dict[uuid.UUID, tuple[Optional[Decimal], Optional[Decimal]]] = {}
        summary_items: List[RemainingStockSummaryItem] = []

        for _, group_rows in groups.items():
            ordered = sorted(
                group_rows,
                key=lambda r: (
                    r["movement_date"],
                    r["created_at"],
                    str(r["movement_id"]),
                ),
            )
            cumulative_qty = Decimal("0.0000")
            running_wac: Optional[Decimal] = None
            total_in = Decimal("0.0000")
            total_out = Decimal("0.0000")
            last_row: Optional[Dict[str, Any]] = None
            last_wac: Optional[Decimal] = None

            for row in ordered:
                movement_type = row.get("movement_type", "IN")
                qty = Decimal(str(row.get("quantity", "0.0000")))
                raw_unit_price = row.get("unit_price")
                unit_price = (
                    Decimal(str(raw_unit_price)) if raw_unit_price is not None else None
                )
                prev_qty = cumulative_qty

                if movement_type == "IN":
                    total_in += qty
                    if unit_price is not None:
                        if running_wac is not None and prev_qty > Decimal("0"):
                            running_wac = (
                                (prev_qty * running_wac) + (qty * unit_price)
                            ) / (prev_qty + qty)
                        else:
                            running_wac = unit_price
                    cumulative_qty = prev_qty + qty
                else:
                    total_out += qty
                    cumulative_qty = prev_qty - qty

                raw_rb = row.get("running_balance")
                row_remaining_qty = (
                    Decimal(str(raw_rb)).quantize(Decimal("0.0001"))
                    if raw_rb is not None
                    else cumulative_qty.quantize(Decimal("0.0001"))
                )

                wac_display = (
                    running_wac.quantize(Decimal("0.0001"))
                    if running_wac is not None
                    else None
                )
                row_rem_val = (
                    (row_remaining_qty * running_wac).quantize(Decimal("0.01"))
                    if running_wac is not None
                    else None
                )

                per_movement[row["movement_id"]] = (wac_display, row_rem_val)
                last_row = row
                last_wac = wac_display

            if last_row is not None:
                summary_remaining_qty = (total_in - total_out).quantize(Decimal("0.0001"))
                summary_rem_val = (
                    (summary_remaining_qty * last_wac).quantize(Decimal("0.01"))
                    if last_wac is not None
                    else None
                )
                summary_items.append(
                    RemainingStockSummaryItem(
                        item_id=last_row["item_id"],
                        item_code=last_row["item_code"],
                        description=last_row["item_description"],
                        category_name=last_row["category_name"],
                        unit=last_row["unit"],
                        warehouse_id=last_row["warehouse_id"],
                        warehouse_code=last_row["warehouse_code"],
                        warehouse_name=last_row["warehouse_name"],
                        project_name=last_row.get("project_name"),
                        total_in=total_in.quantize(Decimal("0.0001")),
                        total_out=total_out.quantize(Decimal("0.0001")),
                        remaining_qty=summary_remaining_qty,
                        weighted_avg_unit_price=last_wac,
                        remaining_value=summary_rem_val,
                    )
                )

        summary_items.sort(key=lambda s: (s.warehouse_code, s.item_code))
        total_remaining_qty = sum(
            (s.remaining_qty for s in summary_items),
            Decimal("0.0000"),
        ).quantize(Decimal("0.0001"))
        total_remaining_value = sum(
            (s.remaining_value for s in summary_items if s.remaining_value is not None),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))

        return per_movement, summary_items, total_remaining_qty, total_remaining_value

    def _map_trial_balance_item(
        self,
        row: Dict[str, Any],
        wac_metrics: Optional[tuple[Optional[Decimal], Optional[Decimal]]] = None,
    ) -> TrialBalanceItem:
        """Converts raw query dictionary into a validated TrialBalanceItem."""
        movement_type = row.get("movement_type", "IN")
        quantity = Decimal(str(row.get("quantity", "0.0000")))
        if movement_type == "IN":
            in_qty = quantity
            out_qty = Decimal("0.0000")
        else:
            in_qty = Decimal("0.0000")
            out_qty = quantity

        raw_unit_price = row.get("unit_price")
        unit_price = (
            Decimal(str(raw_unit_price)).quantize(Decimal("0.0001"))
            if raw_unit_price is not None
            else None
        )
        total_price = (
            (unit_price * quantity).quantize(Decimal("0.0001"))
            if unit_price is not None
            else None
        )
        wac_price, rem_value = wac_metrics if wac_metrics is not None else (None, None)

        return TrialBalanceItem(
            movement_id=row["movement_id"],
            movement_date=row["movement_date"],
            created_at=row["created_at"],
            transaction_id=row["transaction_id"],
            transaction_number=row["transaction_number"],
            transaction_type=row["transaction_type"],
            reference_number=self._resolve_reference_number(row),
            invoice_no=row.get("invoice_no"),
            received_grv_no=row.get("received_grv_no"),
            siv_no=row.get("siv_no"),
            requested_no=row.get("requested_no"),
            istv_no=row.get("istv_no"),
            istrv_no=row.get("istrv_no"),
            external_reference=row.get("external_reference"),
            item_id=row["item_id"],
            item_code=row["item_code"],
            item_description=row["item_description"],
            category_name=row["category_name"],
            unit=row["unit"],
            warehouse_id=row["warehouse_id"],
            warehouse_code=row["warehouse_code"],
            warehouse_name=row["warehouse_name"],
            project_name=row.get("project_name"),
            plate_no=row.get("plate_no"),
            driver_name=row.get("driver_name"),
            in_quantity=in_qty,
            out_quantity=out_qty,
            signed_quantity=Decimal(str(row.get("signed_quantity", "0.0000"))),
            running_balance=(
                Decimal(str(row["running_balance"]))
                if row.get("running_balance") is not None
                else None
            ),
            status=row.get("status", "POSTED"),
            entered_by_name=row.get("entered_by_name", "System"),
            unit_price=unit_price,
            total_price=total_price,
            weighted_avg_unit_price=wac_price,
            remaining_value=rem_value,
        )

    async def get_trial_balance_report(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        project_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        transaction_type: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> TrialBalanceResponse:
        """Generates paginated Trial Balance response with chronological WAC and Remaining Stock Summary."""
        page = max(1, page)
        page_size = max(1, min(page_size, 500))
        offset = (page - 1) * page_size

        rows, total_count, total_in, total_out = await self.repo.get_trial_balance(
            date_from=date_from,
            date_to=date_to,
            warehouse_id=warehouse_id,
            project_id=project_id,
            item_id=item_id,
            category_id=category_id,
            transaction_type=transaction_type,
            search=search,
            limit=page_size,
            offset=offset,
        )

        # Fetch unpaginated filtered movements when results span multiple pages so
        # chronological WAC and Remaining Stock Summary are never skewed by page slicing.
        if offset == 0 and len(rows) >= total_count:
            all_rows = rows
        else:
            all_rows = await self.repo.get_all_trial_balance_movements(
                date_from=date_from,
                date_to=date_to,
                warehouse_id=warehouse_id,
                project_id=project_id,
                item_id=item_id,
                category_id=category_id,
                transaction_type=transaction_type,
                search=search,
            )

        per_movement_wac, remaining_summary, total_remaining_qty, total_remaining_value = (
            self._compute_wac_and_summary(all_rows)
        )

        items = [
            self._map_trial_balance_item(r, per_movement_wac.get(r["movement_id"]))
            for r in rows
        ]
        total_valuation = sum(
            (item.total_price for item in items if item.total_price is not None),
            Decimal("0.0000"),
        )
        return TrialBalanceResponse(
            total_count=total_count,
            page=page,
            page_size=page_size,
            items=items,
            total_in=total_in,
            total_out=total_out,
            total_valuation=total_valuation,
            total_remaining_qty=total_remaining_qty,
            total_remaining_value=total_remaining_value,
            remaining_summary=remaining_summary,
        )

    def _auto_fit_columns(self, ws: Any) -> None:
        """Auto-adjusts column widths based on cell lengths while skipping title banner rows."""
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.row in (1, 2):
                    continue
                val = cell.value
                if val is not None:
                    max_len = max(max_len, len(str(val)))
            ws.column_dimensions[col_letter].width = max(max_len + 3, 10)

    async def export_trial_balance_excel(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        project_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        transaction_type: Optional[str] = None,
        search: Optional[str] = None,
        view: Optional[str] = None,
    ) -> io.BytesIO:
        """
        Exports the filtered trial balance and deduplicated Remaining Stock Summary
        into a formatted Excel workbook. When view == 'remaining', exports only the
        single 'Remaining Stock Summary' sheet; otherwise exports both sheets.
        """
        raw_rows = await self.repo.get_all_trial_balance_movements(
            date_from=date_from,
            date_to=date_to,
            warehouse_id=warehouse_id,
            project_id=project_id,
            item_id=item_id,
            category_id=category_id,
            transaction_type=transaction_type,
            search=search,
        )
        per_movement_wac, remaining_summary, total_remaining_qty, total_remaining_value = (
            self._compute_wac_and_summary(raw_rows)
        )

        is_remaining_only = (view or "").strip().lower() == "remaining"
        wb = openpyxl.Workbook()

        # Define Styles
        title_font = Font(name="Calibri", size=16, bold=True, color="1F497D")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        total_font = Font(name="Calibri", size=11, bold=True)
        total_fill = PatternFill(start_color="E9EDF4", end_color="E9EDF4", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )
        double_bottom_border = Border(
            top=Side(style="thin", color="000000"),
            bottom=Side(style="double", color="000000"),
        )
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if not is_remaining_only:
            ws = wb.active
            ws.title = "Trial Balance"

            # Sheet 1: Title Block (22 columns: A..V)
            ws.merge_cells("A1:V1")
            title_cell = ws["A1"]
            title_cell.value = "DETAILED INVENTORY MOVEMENT / TRIAL BALANCE"
            title_cell.font = title_font
            title_cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[1].height = 28

            # Metadata Row
            ws.merge_cells("A2:V2")
            sub_cell = ws["A2"]
            sub_cell.value = f"Generated: {generated_at} | Total Records: {len(raw_rows)}"
            sub_cell.font = Font(name="Calibri", size=10, italic=True, color="595959")
            sub_cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[2].height = 18

            # Sheet 1 Headers
            headers = [
                "Date",
                "Tx Number",
                "Type",
                "Ref / Doc No",
                "Item Code",
                "Description",
                "Category",
                "Unit",
                "WH Code",
                "Warehouse Name",
                "Project",
                "Vehicle Plate No",
                "Driver Name",
                "IN",
                "OUT",
                "Remaining Qty",
                "Unit Price (ETB)",
                "Total Value (ETB)",
                "Weighted Avg Price (ETB)",
                "Remaining Value (ETB)",
                "Status",
                "Entered By",
            ]

            ws.append([])  # blank row 3
            ws.append(headers)  # row 4
            ws.row_dimensions[4].height = 24

            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=4, column=col_idx)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thin_border

            # Data Rows
            sum_in = Decimal("0.0000")
            sum_out = Decimal("0.0000")
            sum_val = Decimal("0.0000")

            for row_dict in raw_rows:
                item = self._map_trial_balance_item(
                    row_dict, per_movement_wac.get(row_dict["movement_id"])
                )
                sum_in += item.in_quantity
                sum_out += item.out_quantity
                if item.total_price is not None:
                    sum_val += item.total_price

                row_data = [
                    item.movement_date.strftime("%Y-%m-%d"),
                    item.transaction_number,
                    item.transaction_type,
                    item.reference_number or "",
                    item.item_code,
                    item.item_description,
                    item.category_name,
                    item.unit,
                    item.warehouse_code,
                    item.warehouse_name,
                    item.project_name or "",
                    item.plate_no or "",
                    item.driver_name or "",
                    float(item.in_quantity),
                    float(item.out_quantity),
                    float(item.running_balance) if item.running_balance is not None else "",
                    float(item.unit_price) if item.unit_price is not None else "",
                    float(item.total_price) if item.total_price is not None else "",
                    float(item.weighted_avg_unit_price) if item.weighted_avg_unit_price is not None else "",
                    float(item.remaining_value) if item.remaining_value is not None else "",
                    item.status,
                    item.entered_by_name,
                ]
                ws.append(row_data)
                current_row = ws.max_row
                ws.row_dimensions[current_row].height = 19

                for col_idx in range(1, len(headers) + 1):
                    cell = ws.cell(row=current_row, column=col_idx)
                    cell.border = thin_border
                    cell.font = Font(name="Calibri", size=10)
                    if col_idx in (14, 15, 16):
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        cell.number_format = "#,##0.0000"
                    elif col_idx in (17, 18, 19, 20):
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        cell.number_format = "#,##0.00"
                    elif col_idx in (1, 3, 8, 9, 21):
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    else:
                        cell.alignment = Alignment(horizontal="left", vertical="center")

            # Sheet 1 Total Row (leave Remaining Qty / Remaining Value blank to avoid double-counting snapshots)
            total_row_idx = ws.max_row + 1
            ws.append(
                [
                    "TOTAL",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    float(sum_in),
                    float(sum_out),
                    "",
                    "",
                    float(sum_val),
                    "",
                    "",
                    "",
                    "",
                ]
            )
            ws.row_dimensions[total_row_idx].height = 22
            ws.merge_cells(f"A{total_row_idx}:M{total_row_idx}")
            total_label = ws[f"A{total_row_idx}"]
            total_label.alignment = Alignment(horizontal="right", vertical="center")

            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=total_row_idx, column=col_idx)
                cell.font = total_font
                cell.fill = total_fill
                cell.border = double_bottom_border
                if col_idx in (14, 15):
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    cell.number_format = "#,##0.0000"
                elif col_idx == 18:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    cell.number_format = "#,##0.00"

            self._auto_fit_columns(ws)

            ws_summary = wb.create_sheet(title="Remaining Stock Summary")
        else:
            ws_summary = wb.active
            ws_summary.title = "Remaining Stock Summary"

        # Remaining Stock Summary sheet (12 columns: A..L)
        ws_summary.merge_cells("A1:L1")
        sum_title = ws_summary["A1"]
        sum_title.value = "REMAINING STOCK SUMMARY & WEIGHTED AVERAGE VALUATION"
        sum_title.font = title_font
        sum_title.alignment = Alignment(horizontal="center", vertical="center")
        ws_summary.row_dimensions[1].height = 28

        ws_summary.merge_cells("A2:L2")
        sum_sub = ws_summary["A2"]
        sum_sub.value = (
            f"Generated: {generated_at} | Distinct Items / Warehouses: {len(remaining_summary)}"
        )
        sum_sub.font = Font(name="Calibri", size=10, italic=True, color="595959")
        sum_sub.alignment = Alignment(horizontal="center", vertical="center")
        ws_summary.row_dimensions[2].height = 18

        summary_headers = [
            "Item Code",
            "Description",
            "Category",
            "Unit",
            "WH Code",
            "Warehouse Name",
            "Project",
            "Total IN",
            "Total OUT",
            "Remaining Qty",
            "Weighted Avg Price (ETB)",
            "Remaining Value (ETB)",
        ]
        ws_summary.append([])  # blank row 3
        ws_summary.append(summary_headers)  # row 4
        ws_summary.row_dimensions[4].height = 24

        for col_idx in range(1, len(summary_headers) + 1):
            cell = ws_summary.cell(row=4, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

        sum_summary_in = Decimal("0.0000")
        sum_summary_out = Decimal("0.0000")

        for s in remaining_summary:
            sum_summary_in += s.total_in
            sum_summary_out += s.total_out
            ws_summary.append(
                [
                    s.item_code,
                    s.description,
                    s.category_name,
                    s.unit,
                    s.warehouse_code,
                    s.warehouse_name,
                    s.project_name or "",
                    float(s.total_in),
                    float(s.total_out),
                    float(s.remaining_qty),
                    float(s.weighted_avg_unit_price)
                    if s.weighted_avg_unit_price is not None
                    else "",
                    float(s.remaining_value) if s.remaining_value is not None else "",
                ]
            )
            current_row = ws_summary.max_row
            ws_summary.row_dimensions[current_row].height = 19
            for col_idx in range(1, len(summary_headers) + 1):
                cell = ws_summary.cell(row=current_row, column=col_idx)
                cell.border = thin_border
                cell.font = Font(name="Calibri", size=10)
                if col_idx in (8, 9, 10):
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    cell.number_format = "#,##0.0000"
                elif col_idx in (11, 12):
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    cell.number_format = "#,##0.00"
                elif col_idx in (4, 5):
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

        sum_total_row = ws_summary.max_row + 1
        ws_summary.append(
            [
                "TOTAL",
                "",
                "",
                "",
                "",
                "",
                "",
                float(sum_summary_in),
                float(sum_summary_out),
                float(total_remaining_qty),
                "",
                float(total_remaining_value),
            ]
        )
        ws_summary.row_dimensions[sum_total_row].height = 22
        ws_summary.merge_cells(f"A{sum_total_row}:G{sum_total_row}")
        ws_summary[f"A{sum_total_row}"].alignment = Alignment(
            horizontal="right", vertical="center"
        )

        for col_idx in range(1, len(summary_headers) + 1):
            cell = ws_summary.cell(row=sum_total_row, column=col_idx)
            cell.font = total_font
            cell.fill = total_fill
            cell.border = double_bottom_border
            if col_idx in (8, 9, 10):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = "#,##0.0000"
            elif col_idx == 12:
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = "#,##0.00"

        self._auto_fit_columns(ws_summary)

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream

    async def get_stock_balance_report(
        self,
        warehouse_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
    ) -> StockBalanceResponse:
        """Returns current stock balances with calculated available quantities."""
        rows = await self.repo.get_current_stock_balances(
            warehouse_id=warehouse_id,
            category_id=category_id,
            search=search,
        )
        items = [
            StockBalanceItem(
                warehouse_id=r["warehouse_id"],
                warehouse_code=r["warehouse_code"],
                warehouse_name=r["warehouse_name"],
                project_name=r.get("project_name"),
                category_name=r["category_name"],
                item_id=r["item_id"],
                item_code=r["item_code"],
                item_description=r["item_description"],
                unit=r["unit"],
                quantity_on_hand=Decimal(str(r["quantity_on_hand"])),
                quantity_reserved=Decimal(str(r["quantity_reserved"])),
                quantity_available=Decimal(str(r["quantity_available"])),
            )
            for r in rows
        ]
        return StockBalanceResponse(total_count=len(items), items=items)

    async def get_in_transit_report(
        self,
        source_warehouse_id: Optional[uuid.UUID] = None,
        destination_warehouse_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[InTransitReportItem]:
        """Returns transfer items currently in transit with remaining quantities."""
        rows = await self.repo.get_in_transit_transfers(
            source_warehouse_id=source_warehouse_id,
            destination_warehouse_id=destination_warehouse_id,
            status=status,
            search=search,
        )
        return [
            InTransitReportItem(
                transfer_record_id=r["transfer_record_id"],
                istv_transaction_id=r["istv_transaction_id"],
                istv_number=r["istv_number"],
                istv_no=r.get("istv_no"),
                invoice_no=r.get("invoice_no"),
                transaction_date=r["transaction_date"],
                source_warehouse_id=r.get("source_warehouse_id"),
                source_warehouse_name=r["source_warehouse_name"],
                destination_warehouse_id=r.get("destination_warehouse_id"),
                destination_warehouse_name=r["destination_warehouse_name"],
                plate_no=r.get("plate_no"),
                driver_name=r.get("driver_name"),
                status=r["status"],
                item_id=r["item_id"],
                item_code=r["item_code"],
                item_description=r["item_description"],
                unit=r["unit"],
                sent_quantity=Decimal(str(r["sent_quantity"])),
                received_quantity=Decimal(str(r["received_quantity"])),
                remaining_quantity=Decimal(str(r["remaining_quantity"])),
                unit_price=Decimal(str(r["unit_price"])) if r.get("unit_price") is not None else None,
            )
            for r in rows
        ]
