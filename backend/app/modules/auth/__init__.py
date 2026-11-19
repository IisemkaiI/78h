"""Authentication module (password login, JWT access tokens)."""

from app.modules.auth.dependencies import (
    CurrentUser,
    get_current_user,
    require_permissions,
    require_roles,
)
from app.modules.auth.service import AuthService

__all__ = [
    "AuthService",
    "CurrentUser",
    "get_current_user",
    "require_permissions",
    "require_roles",
]
