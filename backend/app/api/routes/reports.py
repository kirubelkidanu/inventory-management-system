# backend/app/api/routes/reports.py
from datetime import date, datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.report import (
    InTransitReportItem,
    StockBalanceResponse,
    TrialBalanceResponse,
)
from app.security.auth import AuthenticatedUser, get_current_user
from app.services.report import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


async def get_report_service(
    db: AsyncSession = Depends(get_db),
) -> ReportService:
    return ReportService(db)


@router.get(
    "/trial-balance",
    response_model=TrialBalanceResponse,
    summary="Get paginated detailed inventory movement / trial balance report",
)
async def get_trial_balance(
    date_from: Optional[date] = Query(None, description="Filter movements from date (inclusive)"),
    date_to: Optional[date] = Query(None, description="Filter movements to date (inclusive)"),
    warehouse_id: Optional[uuid.UUID] = Query(None, description="Filter by warehouse ID"),
    project_id: Optional[uuid.UUID] = Query(None, description="Filter by project ID"),
    item_id: Optional[uuid.UUID] = Query(None, description="Filter by item ID"),
    category_id: Optional[uuid.UUID] = Query(None, description="Filter by category ID"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type (e.g. GRV, SIV, ISTV, ISTRV, SRV, ADJUSTMENT)"),
    search: Optional[str] = Query(None, description="Search term for item code, description, voucher no, driver, or plate"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=500, description="Page size limit"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    return await service.get_trial_balance_report(
        date_from=date_from,
        date_to=date_to,
        warehouse_id=warehouse_id,
        project_id=project_id,
        item_id=item_id,
        category_id=category_id,
        transaction_type=transaction_type,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/trial-balance/export",
    summary="Export filtered trial balance to formatted Excel (.xlsx) spreadsheet",
)
async def export_trial_balance(
    date_from: Optional[date] = Query(None, description="Filter movements from date (inclusive)"),
    date_to: Optional[date] = Query(None, description="Filter movements to date (inclusive)"),
    warehouse_id: Optional[uuid.UUID] = Query(None, description="Filter by warehouse ID"),
    project_id: Optional[uuid.UUID] = Query(None, description="Filter by project ID"),
    item_id: Optional[uuid.UUID] = Query(None, description="Filter by item ID"),
    category_id: Optional[uuid.UUID] = Query(None, description="Filter by category ID"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    search: Optional[str] = Query(None, description="Search term"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    excel_stream = await service.export_trial_balance_excel(
        date_from=date_from,
        date_to=date_to,
        warehouse_id=warehouse_id,
        project_id=project_id,
        item_id=item_id,
        category_id=category_id,
        transaction_type=transaction_type,
        search=search,
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"trial_balance_{timestamp}.xlsx"

    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/stock-balances",
    response_model=StockBalanceResponse,
    summary="Get current stock balances with available inventory calculations",
)
async def get_stock_balances(
    warehouse_id: Optional[uuid.UUID] = Query(None, description="Filter by warehouse ID"),
    category_id: Optional[uuid.UUID] = Query(None, description="Filter by category ID"),
    search: Optional[str] = Query(None, description="Search item code, description, or warehouse name"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    return await service.get_stock_balance_report(
        warehouse_id=warehouse_id,
        category_id=category_id,
        search=search,
    )


@router.get(
    "/in-transit",
    response_model=List[InTransitReportItem],
    summary="Get in-transit transfer lines with remaining quantity tracking",
)
async def get_in_transit(
    source_warehouse_id: Optional[uuid.UUID] = Query(None, description="Filter by source warehouse ID"),
    destination_warehouse_id: Optional[uuid.UUID] = Query(None, description="Filter by destination warehouse ID"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. IN_TRANSIT, PARTIALLY_RECEIVED, COMPLETED)"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    return await service.get_in_transit_report(
        source_warehouse_id=source_warehouse_id,
        destination_warehouse_id=destination_warehouse_id,
        status=status,
    )
