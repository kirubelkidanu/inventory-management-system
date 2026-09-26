# backend/app/api/routes/transactions.py
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.transaction import (
    AdjustmentCreate,
    GRVCreate,
    ISTRVCreate,
    ISTVCreate,
    SIVCreate,
    SRVCreate,
    TransactionRead,
    TransferRecordRead,
)
from app.security.auth import AuthenticatedUser, get_current_user, require_roles
from app.services.transaction import TransactionService

router = APIRouter(prefix="/transactions", tags=["transactions"])


async def get_transaction_service(
    db: AsyncSession = Depends(get_db),
) -> TransactionService:
    return TransactionService(db)


@router.post(
    "/grv",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create and post Goods Receiving Voucher (GRV)",
)
async def create_grv(
    payload: GRVCreate,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER")
    ),
    service: TransactionService = Depends(get_transaction_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    return await service.create_and_post_grv(user_id=user_id, payload=payload)


@router.post(
    "/siv",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create and post Store Issue Voucher (SIV)",
)
async def create_siv(
    payload: SIVCreate,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER")
    ),
    service: TransactionService = Depends(get_transaction_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    return await service.create_and_post_siv(user_id=user_id, payload=payload)


@router.post(
    "/istv",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create and post Inter-Store Transfer Voucher (ISTV)",
)
async def create_istv(
    payload: ISTVCreate,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER")
    ),
    service: TransactionService = Depends(get_transaction_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    return await service.create_and_post_istv(user_id=user_id, payload=payload)


@router.post(
    "/istrv",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create and post Inter-Store Transfer Receiving Voucher (ISTRV)",
)
async def create_istrv(
    payload: ISTRVCreate,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER")
    ),
    service: TransactionService = Depends(get_transaction_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    return await service.create_and_post_istrv(user_id=user_id, payload=payload)


@router.post(
    "/srv",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create and post Store Return Voucher (SRV)",
)
async def create_srv(
    payload: SRVCreate,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER")
    ),
    service: TransactionService = Depends(get_transaction_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    return await service.create_and_post_srv(user_id=user_id, payload=payload)


@router.post(
    "/adjustment",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create and post Stock Adjustment (ADJUSTMENT)",
)
async def create_adjustment(
    payload: AdjustmentCreate,
    current_user: AuthenticatedUser = Depends(
        require_roles("ADMIN", "INVENTORY_MANAGER")
    ),
    service: TransactionService = Depends(get_transaction_service),
):
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None)
    return await service.create_and_post_adjustment(user_id=user_id, payload=payload)


@router.get(
    "/transfers/{istv_id}",
    response_model=TransferRecordRead,
    summary="Get transfer record and in-transit tracking by ISTV ID",
)
async def get_transfer_record(
    istv_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service),
):
    transfer = await service.get_transfer_record_by_istv_id(istv_id)
    if transfer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transfer record for ISTV {istv_id} not found.",
        )
    return transfer


@router.get(
    "",
    response_model=List[TransactionRead],
    summary="List transactions with filters and pagination",
)
async def list_transactions(
    transaction_type: Optional[str] = Query(None, description="Filter by type (GRV, SIV, ISTV, ISTRV, SRV, ADJUSTMENT)"),
    warehouse_id: Optional[uuid.UUID] = Query(None, description="Filter by warehouse ID"),
    search: Optional[str] = Query(None, description="Search transaction number, supplier, invoice, plate, driver, remarks"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service),
):
    return await service.list_transactions(
        transaction_type=transaction_type,
        warehouse_id=warehouse_id,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionRead,
    summary="Get transaction by ID with line items",
)
async def get_transaction(
    transaction_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service),
):
    transaction = await service.repo.get_transaction_by_id(transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found.",
        )
    return transaction

