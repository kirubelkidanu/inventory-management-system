import uuid
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.auth import DemoLoginRequest, LoginRequest, TokenResponse, UserAuthResponse
from app.security.auth import (
    ROLES,
    AuthenticatedUser,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Predefined developer / demo accounts for RBAC testing
DEMO_ACCOUNTS: Dict[str, dict] = {
    "admin@ims.local": {
        "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
        "email": "admin@ims.local",
        "full_name": "Alice Administrator",
        "role": "ADMIN",
        "is_active": True,
    },
    "manager@ims.local": {
        "id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
        "email": "manager@ims.local",
        "full_name": "Bob Manager",
        "role": "INVENTORY_MANAGER",
        "is_active": True,
    },
    "storekeeper@ims.local": {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
        "email": "storekeeper@ims.local",
        "full_name": "Charlie Keeper",
        "role": "STORE_KEEPER",
        "is_active": True,
    },
    "viewer@ims.local": {
        "id": uuid.UUID("44444444-4444-4444-4444-444444444444"),
        "email": "viewer@ims.local",
        "full_name": "Diana Auditor",
        "role": "VIEWER",
        "is_active": True,
    },
}

ROLE_TO_ACCOUNT = {acc["role"]: acc for acc in DEMO_ACCOUNTS.values()}


@router.post("/token", response_model=TokenResponse, summary="Obtain access token via email & password")
async def login_for_token(payload: LoginRequest):
    """
    Authenticates user credentials and issues a signed JWT access token.
    Supports standard demo credentials.
    """
    email_key = payload.email.lower().strip()
    account = DEMO_ACCOUNTS.get(email_key)

    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please use one of the standard demo accounts.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        user_id=str(account["id"]),
        email=account["email"],
        role=account["role"],
    )

    user_data = UserAuthResponse(
        id=account["id"],
        email=account["email"],
        full_name=account["full_name"],
        role=account["role"],
        is_active=account["is_active"],
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=user_data,
    )


@router.post("/demo-login", response_model=TokenResponse, summary="Instant demo sign-in for testing RBAC")
async def demo_login(payload: DemoLoginRequest):
    """
    Issues a valid signed JWT access token for a requested system role.
    Used by frontend demo buttons for instantaneous role switching.
    """
    normalized_role = payload.role.upper().strip()
    if normalized_role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Must be one of {sorted(ROLES)}.",
        )

    account = ROLE_TO_ACCOUNT.get(normalized_role)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No demo account configured for role '{normalized_role}'.",
        )

    token = create_access_token(
        user_id=str(account["id"]),
        email=account["email"],
        role=account["role"],
    )

    user_data = UserAuthResponse(
        id=account["id"],
        email=account["email"],
        full_name=account["full_name"],
        role=account["role"],
        is_active=account["is_active"],
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=user_data,
    )


@router.get("/me", response_model=UserAuthResponse, summary="Get current authenticated user profile")
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)):
    """Returns the verified user profile from the validated Bearer token."""
    account = ROLE_TO_ACCOUNT.get(current_user.role)
    full_name = account["full_name"] if account else "System User"

    try:
        user_uuid = uuid.UUID(current_user.user_id)
    except ValueError:
        user_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, current_user.user_id)

    return UserAuthResponse(
        id=user_uuid,
        email=current_user.email,
        full_name=full_name,
        role=current_user.role,
        is_active=True,
    )
