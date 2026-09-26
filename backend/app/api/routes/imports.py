# backend/app/api/routes/imports.py
from typing import Any, Dict
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.import_ import (
    ImportBatchPreview,
    ImportBatchRead,
    InitialStockBatchPreview,
)
from app.security.auth import AuthenticatedUser, require_roles
from app.services.import_ import ImportService

router = APIRouter(prefix="/imports", tags=["imports"])


async def get_import_service(
    db: AsyncSession = Depends(get_db),
) -> ImportService:
    return ImportService(db)


@router.post(
    "/items/upload",
    response_model=ImportBatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and stage Item Master spreadsheet (.xlsx or .csv)",
)
async def upload_item_master_file(
    file: UploadFile = File(..., description="Spreadsheet file (.xlsx or .csv)"),
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER")
    ),
    service: ImportService = Depends(get_import_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )
    return await service.stage_item_master_file(
        user_id=user_id,
        file_name=file.filename or "item_master.xlsx",
        file_bytes=file_bytes,
    )


@router.get(
    "/batches/{batch_id}",
    response_model=ImportBatchPreview,
    summary="Get import batch status, errors, and preview of staged items",
)
async def get_batch_preview(
    batch_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER")
    ),
    service: ImportService = Depends(get_import_service),
):
    return await service.get_batch_preview(batch_id=batch_id)


@router.post(
    "/batches/{batch_id}/commit",
    summary="Commit valid staged items from an import batch into the Item Master catalog",
)
async def commit_batch(
    batch_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER")
    ),
    service: ImportService = Depends(get_import_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    return await service.commit_item_master_import(
        user_id=user_id,
        batch_id=batch_id,
    )


@router.post(
    "/initial-stock/upload",
    response_model=ImportBatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and stage Initial Stock spreadsheet (.xlsx or .csv)",
)
async def upload_initial_stock_file(
    file: UploadFile = File(..., description="Initial stock spreadsheet (.xlsx or .csv)"),
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER")
    ),
    service: ImportService = Depends(get_import_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )
    return await service.stage_initial_stock_file(
        user_id=user_id,
        file_name=file.filename or "initial_stock.xlsx",
        file_bytes=file_bytes,
    )


@router.get(
    "/initial-stock/{batch_id}",
    response_model=InitialStockBatchPreview,
    summary="Get initial stock import batch status, errors, and preview of staged rows",
)
async def get_initial_stock_preview(
    batch_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER")
    ),
    service: ImportService = Depends(get_import_service),
):
    return await service.get_initial_stock_batch_preview(batch_id=batch_id)


@router.post(
    "/initial-stock/{batch_id}/commit",
    summary="Commit valid staged initial stock from an import batch into inventory balances and ledger",
)
async def commit_initial_stock_batch(
    batch_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER")
    ),
    service: ImportService = Depends(get_import_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    return await service.commit_initial_stock_import(
        user_id=user_id,
        batch_id=batch_id,
    )
