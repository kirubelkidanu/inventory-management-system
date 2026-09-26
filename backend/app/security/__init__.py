"""Authentication and authorization foundation package.

This project intentionally keeps the auth utility as a reusable foundation for
future protected endpoints without implementing business routes or policies.
"""

from app.security.auth import AuthenticatedUser, ROLES, get_current_user, require_roles

__all__ = ["AuthenticatedUser", "ROLES", "get_current_user", "require_roles"]

