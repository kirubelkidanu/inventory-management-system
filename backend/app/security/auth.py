"""Authentication and authorization utilities re-exported from app.dependencies."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt

from app.core.config import settings
from app.dependencies import get_current_user, require_role, require_roles, ROLES
from app.models.user import User

# Backward compatibility alias
AuthenticatedUser = User


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Creates a signed HS256 JWT access token for test suites."""
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
    jwt_secret = settings.SUPABASE_JWT_SECRET or settings.JWT_SECRET
    return jwt.encode(payload, jwt_secret, algorithm=settings.JWT_ALGORITHM)

__all__ = ["AuthenticatedUser", "User", "get_current_user", "require_role", "require_roles", "ROLES", "create_access_token"]
