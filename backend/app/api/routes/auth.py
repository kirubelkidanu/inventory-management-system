import uuid
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    auth_user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


@router.get("/me", response_model=UserProfileResponse, summary="Get current authenticated user profile")
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the verified user profile from public.users for the authenticated Supabase user.
    """
    uid = current_user.id
    if isinstance(uid, str):
        try:
            uid = uuid.UUID(uid)
        except Exception:
            uid = uuid.uuid5(uuid.NAMESPACE_DNS, uid)

    auth_uid = current_user.auth_user_id
    if isinstance(auth_uid, str):
        try:
            auth_uid = uuid.UUID(auth_uid)
        except Exception:
            auth_uid = uuid.uuid5(uuid.NAMESPACE_DNS, auth_uid)

    return UserProfileResponse(
        id=uid,
        auth_user_id=auth_uid,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
    )
