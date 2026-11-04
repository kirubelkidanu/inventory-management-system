from datetime import date
from typing import Any, Dict, List, Optional
# backend/app/api/routes/imports.py
import uuid

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
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
@router.post(
    "/items/upload/",
    response_model=ImportBatchRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
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


@router.post(
    "/items/stage",
    response_model=ImportBatchPreview,
    status_code=status.HTTP_200_OK,
    summary="Stage, validate, and preview Item Master spreadsheet (.xlsx or .csv)",
)
@router.post(
    "/items/stage/",
    response_model=ImportBatchPreview,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def stage_item_master_file(
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
    batch = await service.stage_item_master_file(
        user_id=user_id,
        file_name=file.filename or "item_master.xlsx",
        file_bytes=file_bytes,
    )
    return await service.get_batch_preview(batch_id=batch.id)


@router.get(
    "/batches/{batch_id}",
    response_model=ImportBatchPreview,
    summary="Get import batch status, errors, and preview of staged items",
)
@router.get(
    "/batches/{batch_id}/",
    response_model=ImportBatchPreview,
    include_in_schema=False,
)
@router.get(
    "/items/{batch_id}",
    response_model=ImportBatchPreview,
    summary="Get import batch status, errors, and preview of staged items",
)
@router.get(
    "/items/{batch_id}/",
    response_model=ImportBatchPreview,
    include_in_schema=False,
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
    summary="Commit valid staged items from an import batch into the Item Master catalog or ledger",
)
@router.post(
    "/batches/{batch_id}/commit/",
    include_in_schema=False,
)
@router.post(
    "/items/{batch_id}/commit",
    summary="Commit valid staged items from an import batch into the Item Master catalog",
)
@router.post(
    "/items/{batch_id}/commit/",
    include_in_schema=False,
)
@router.post(
    "/{batch_id}/commit",
    summary="Commit valid staged items from an import batch",
    include_in_schema=False,
)
@router.post(
    "/{batch_id}/commit/",
    include_in_schema=False,
)
async def commit_batch(
    batch_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER")
    ),
    service: ImportService = Depends(get_import_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    try:
        batch = None
        if hasattr(service, "repo") and hasattr(service.repo, "get_batch_by_id"):
            batch = await service.repo.get_batch_by_id(batch_id)
        if batch and getattr(batch, "import_type", None) == "INITIAL_STOCK":
            return await service.commit_initial_stock_import(
                user_id=user_id,
                batch_id=batch_id,
            )
        if hasattr(service, "commit_item_master_import"):
            return await service.commit_item_master_import(
                user_id=user_id,
                batch_id=batch_id,
            )
        elif hasattr(service, "commit_batch"):
            return await service.commit_batch(
                user_id=user_id,
                batch_id=batch_id,
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to commit import batch: {str(e)}",
        )


@router.post(
    "/initial-stock/upload",
    response_model=ImportBatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and stage Initial Stock spreadsheet (.xlsx or .csv)",
)
@router.post(
    "/initial-stock/upload/",
    response_model=ImportBatchRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
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
    "/initial-stock/batches",
    response_model=List[ImportBatchRead],
    summary="List all initial stock import batches",
)
@router.get(
    "/initial-stock/batches/",
    response_model=List[ImportBatchRead],
    include_in_schema=False,
)
async def list_initial_stock_batches(
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER")
    ),
    service: ImportService = Depends(get_import_service),
):
    batches = await service.list_initial_stock_batches()
    return [ImportBatchRead.model_validate(b) for b in batches]

@router.get(
    "/initial-stock/{batch_id}",
    response_model=InitialStockBatchPreview,
    summary="Get initial stock import batch status, errors, and preview of staged rows",
)
@router.get(
    "/initial-stock/{batch_id}/",
    response_model=InitialStockBatchPreview,
    include_in_schema=False,
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
@router.post(
    "/initial-stock/{batch_id}/commit/",
    include_in_schema=False,
)
@router.post(
    "/initial-stock/commit/{batch_id}",
    include_in_schema=False,
)
@router.post(
    "/initial-stock/commit/{batch_id}/",
    include_in_schema=False,
)
async def commit_initial_stock_batch(
    batch_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER")
    ),
    service: ImportService = Depends(get_import_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    try:
        return await service.commit_initial_stock_import(
            user_id=user_id,
            batch_id=batch_id,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to commit initial stock import: {str(e)}",
        )

@router.post(
    "/initial-stock/stage",
    response_model=ImportBatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Stage, validate, and preview Initial Stock spreadsheet with 4-column support",
)
@router.post(
    "/initial-stock/stage/",
    response_model=ImportBatchRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def stage_initial_stock_file(
    file: UploadFile = File(..., description="Spreadsheet file (.xlsx or .csv)"),
    warehouse_id: Optional[uuid.UUID] = Form(None),
    project_id: Optional[uuid.UUID] = Form(None),
    transaction_date: Optional[date] = Form(None),
    remarks: Optional[str] = Form(None),
    fallback_to_catalog_uom: bool = Form(True),
    x_warehouse_id: Optional[uuid.UUID] = Header(None, alias="warehouse_id"),
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
    effective_wh_id = warehouse_id or x_warehouse_id
    try:
        batch = await service.stage_initial_stock_file(
            user_id=user_id,
            file_name=file.filename or "initial_stock.xlsx",
            file_bytes=file_bytes,
            warehouse_id=effective_wh_id,
            project_id=project_id,
            transaction_date=transaction_date,
            remarks=remarks,
            fallback_to_catalog_uom=fallback_to_catalog_uom,
        )
    except TypeError:
        batch = await service.stage_initial_stock_file(
            user_id=user_id,
            file_name=file.filename or "initial_stock.xlsx",
            file_bytes=file_bytes,
        )
    return batch



