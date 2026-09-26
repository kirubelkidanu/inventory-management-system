# backend/app/api/routes/reconciliation.py
from typing import Any, Dict
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.reconciliation import (
    CountSheetResponse,
    PhysicalCountSubmitRequest,
    ReconciliationCommitRequest,
    ReconciliationPreviewResponse,
)
from app.security.auth import AuthenticatedUser, require_roles
from app.services.reconciliation import ReconciliationService

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


async def get_reconciliation_service(
    db: AsyncSession = Depends(get_db),
) -> ReconciliationService:
    return ReconciliationService(db)


@router.get(
    "/count-sheet/{warehouse_id}",
    response_model=CountSheetResponse,
    summary="Generate physical count audit sheet template for a warehouse",
)
async def get_count_sheet(
    warehouse_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER")
    ),
    service: ReconciliationService = Depends(get_reconciliation_service),
):
    return await service.generate_count_sheet(warehouse_id=warehouse_id)


@router.post(
    "/preview",
    response_model=ReconciliationPreviewResponse,
    summary="Calculate and preview physical count variances",
)
async def preview_physical_count(
    payload: PhysicalCountSubmitRequest,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER")
    ),
    service: ReconciliationService = Depends(get_reconciliation_service),
):
    return await service.calculate_variance_preview(payload=payload)


@router.post(
    "/commit",
    summary="Atomically commit physical count reconciliation adjustments",
)
async def commit_reconciliation(
    payload: ReconciliationCommitRequest,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER")
    ),
    service: ReconciliationService = Depends(get_reconciliation_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    return await service.commit_reconciliation_adjustments(
        user_id=user_id,
        payload=payload,
    )
