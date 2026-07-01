"""
EKOS API Dependencies
Shared dependencies for FastAPI route handlers.
"""

from fastapi import Depends, Header
from app.db.database import get_db
from app.config import get_settings
from app.security.auth import verify_token
from app.utils.exceptions import AuthenticationError
from typing import Optional

settings = get_settings()


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db=Depends(get_db),
):
    """Extract and verify the current user from JWT token."""
    if not authorization:
        raise AuthenticationError("Missing Authorization header")

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError("Invalid Authorization header format")

    token = parts[1]
    payload = verify_token(token, token_type="access")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token: missing user ID")

    if settings.database_provider == "firestore":
        # Firestore: use the session's get() method
        user = await db.get(_get_user_model(), int(user_id))
    else:
        # MySQL: use SQLAlchemy select
        from sqlalchemy import select
        from app.db.models import User
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise AuthenticationError("User account is deactivated")

    return user


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    db=Depends(get_db),
):
    """Get current user if authenticated, None otherwise."""
    if not authorization:
        return None
    try:
        return await get_current_user(authorization=authorization, db=db)
    except AuthenticationError:
        return None


def _get_user_model():
    """Return the correct User model class based on database provider."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import User
        return User
    else:
        from app.db.models import User
        return User
