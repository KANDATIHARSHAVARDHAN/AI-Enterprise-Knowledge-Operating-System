"""
EKOS Role-Based Access Control (RBAC)
Defines roles, permissions, and access control decorators.
"""

from enum import Enum
from functools import wraps
from typing import Callable
from app.utils.exceptions import AuthorizationError


class Role(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


# Permission matrix: role → allowed actions
PERMISSIONS = {
    Role.ADMIN: {
        "documents.upload", "documents.list", "documents.delete", "documents.view",
        "query.ask", "query.history", "query.trace",
        "evaluation.view", "evaluation.run",
        "admin.users", "admin.users.update", "admin.users.delete",
        "admin.system", "admin.audit",
    },
    Role.ANALYST: {
        "documents.upload", "documents.list", "documents.view",
        "query.ask", "query.history", "query.trace",
        "evaluation.view", "evaluation.run",
    },
    Role.VIEWER: {
        "documents.list", "documents.view",
        "query.ask", "query.history",
        "evaluation.view",
    },
}


def has_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific permission."""
    try:
        role_enum = Role(role)
    except ValueError:
        return False
    return permission in PERMISSIONS.get(role_enum, set())


def require_permission(permission: str):
    """Decorator to enforce permission checks on route handlers."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # The current_user should be injected via FastAPI dependency
            current_user = kwargs.get("current_user")
            if not current_user:
                raise AuthorizationError("No authenticated user")

            user_role = getattr(current_user, "role", "viewer")
            if not has_permission(user_role, permission):
                raise AuthorizationError(
                    f"Role '{user_role}' does not have permission '{permission}'"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(allowed_roles: list[str]):
    """Decorator to restrict access to specific roles."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                raise AuthorizationError("No authenticated user")

            user_role = getattr(current_user, "role", "viewer")
            if user_role not in allowed_roles:
                raise AuthorizationError(
                    f"Role '{user_role}' is not allowed. Required: {allowed_roles}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator
