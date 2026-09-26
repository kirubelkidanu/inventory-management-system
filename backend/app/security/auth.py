"""
Authentication and authorization utilities.

Supabase issues RS256 JWTs signed with a project-specific private key.
For the MVP, we verify using the JWT_SECRET (HS256) to keep local dev simple
without requiring JWKS fetching. Production must switch to RS256 JWKS validation.

Security rules (from docs/SECURITY.md):
- The service-role key is NEVER used here; it stays in config only.
- Role-based access is enforced by backend policy; frontend button-hiding is
  only a UX feature and is NOT a security control.
- Bearer token must be present and valid for all protected endpoints.
"""
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

_bearer_scheme = HTTPBearer(auto_error=True)

# Application roles as defined in docs/SECURITY.md and users table CHECK constraint
ROLES = {"ADMIN", "INVENTORY_MANAGER", "STORE_KEEPER", "VIEWER"}


class AuthenticatedUser:
    """Carries the verified identity extracted from the JWT payload."""

    def __init__(self, user_id: str, email: str, role: str) -> None:
        self.user_id = user_id
        self.email = email
        self.role = role

    def require_role(self, *allowed_roles: str) -> None:
        """Raise HTTP 403 if the user's role is not in allowed_roles."""
        if self.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{self.role}' is not authorized for this operation.",
            )


def require_roles(*allowed_roles: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Reusable authorization dependency for future protected endpoints.

    This does not create business routes or new role policy; it only enforces the
    documented role names already present in the repository and security docs.
    """

    async def dependency(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorized for this operation.",
            )
        return current_user

    return dependency


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> AuthenticatedUser:
    """
    FastAPI dependency: validates the Bearer JWT and returns AuthenticatedUser.
    Raises HTTP 401 if the token is missing, expired, or invalid.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        user_id: str | None = payload.get("sub")
        email: str | None = payload.get("email")
        role: str | None = payload.get("role")

        if not user_id or not role or role not in ROLES:
            raise credentials_exception

        return AuthenticatedUser(
            user_id=user_id,
            email=email or "",
            role=role,
        )
    except JWTError:
        raise credentials_exception


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Creates a signed HS256 JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=7)

    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

