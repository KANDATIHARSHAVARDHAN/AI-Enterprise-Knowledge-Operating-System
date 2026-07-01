"""
EKOS Auth Routes
Handles user registration, login, token refresh, and profile.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.db.database import get_db
from app.config import get_settings
from app.security.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, verify_token,
)
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
settings = get_settings()


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db=Depends(get_db)):
    """Register a new user account."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB, AuditLog
        fs = FirestoreDB()

        # Check if email already exists
        existing = await fs.get_user_by_email(request.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Check if username exists
        existing = await fs.get_user_by_username(request.username)
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")

        # Create user
        user = await fs.create_user({
            "email": request.email,
            "username": request.username,
            "password_hash": hash_password(request.password),
            "full_name": request.full_name,
            "role": "viewer",
        })

        # Create tokens
        token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Audit log
        await fs.create_audit_log({"user_id": user.id, "action": "REGISTER", "resource_type": "auth"})

    else:
        from sqlalchemy import select
        from app.db.models import User, AuditLog

        # Check if email already exists
        result = await db.execute(select(User).where(User.email == request.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        # Check if username exists
        result = await db.execute(select(User).where(User.username == request.username))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already taken")

        # Create user
        user = User(
            email=request.email,
            username=request.username,
            password_hash=hash_password(request.password),
            full_name=request.full_name,
            role="viewer",
        )
        db.add(user)
        await db.flush()

        # Create tokens
        token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Audit log
        db.add(AuditLog(user_id=user.id, action="REGISTER", resource_type="auth"))
        await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
        },
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db=Depends(get_db)):
    """Login with email and password."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        user = await fs.get_user_by_email(request.email)
    else:
        from sqlalchemy import select
        from app.db.models import User, AuditLog
        result = await db.execute(select(User).where(User.email == request.email))
        user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        await fs.create_audit_log({"user_id": user.id, "action": "LOGIN", "resource_type": "auth"})
    else:
        db.add(AuditLog(user_id=user.id, action="LOGIN", resource_type="auth"))
        await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
        },
    )


@router.post("/refresh", response_model=dict)
async def refresh_token(request: RefreshRequest, db=Depends(get_db)):
    """Refresh an access token using a refresh token."""
    payload = verify_token(request.refresh_token, token_type="refresh")
    user_id = payload.get("sub")

    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        user = await fs.get_user(int(user_id))
    else:
        from sqlalchemy import select
        from app.db.models import User
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    new_access_token = create_access_token(token_data)

    return {"access_token": new_access_token, "token_type": "bearer"}


@router.get("/me")
async def get_profile(current_user=Depends(get_current_user)):
    """Get current user profile."""
    created_at = current_user.created_at
    if created_at and hasattr(created_at, 'isoformat'):
        created_at = created_at.isoformat()
    elif isinstance(created_at, (int, float)):
        from datetime import datetime
        created_at = datetime.fromtimestamp(created_at).isoformat()

    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": created_at,
    }
