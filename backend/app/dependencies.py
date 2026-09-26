"""Application dependency exports for the backend."""

from app.core.database import get_db
from app.security.auth import get_current_user

__all__ = ["get_db", "get_current_user"]