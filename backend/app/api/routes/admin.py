"""
EKOS Admin Routes
User management, system stats, and audit logs.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel
from app.db.database import get_db
from app.db.models import User, Document, QueryLog, AuditLog
from app.api.dependencies import get_current_user
from app.db.vector_store import get_vector_store
from app.db.knowledge_graph import get_knowledge_graph

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def _check_admin(user: User):
    """Verify user has admin role."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


class UpdateRoleRequest(BaseModel):
    role: str


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all users (admin only)."""
    _check_admin(current_user)

    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    request: UpdateRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a user's role (admin only)."""
    _check_admin(current_user)

    if request.role not in ["admin", "analyst", "viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = request.role
    db.add(AuditLog(
        user_id=current_user.id,
        action="UPDATE_ROLE",
        resource_type="user",
        resource_id=str(user_id),
        details_json={"new_role": request.role},
    ))
    await db.commit()

    return {"message": f"User {user_id} role updated to {request.role}"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a user (admin only)."""
    _check_admin(current_user)

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    db.add(AuditLog(
        user_id=current_user.id,
        action="DELETE_USER",
        resource_type="user",
        resource_id=str(user_id),
    ))
    await db.commit()

    return {"message": f"User {user_id} deleted"}


@router.get("/system/stats")
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get system-wide statistics."""
    _check_admin(current_user)

    user_count = await db.execute(select(func.count(User.id)))
    doc_count = await db.execute(select(func.count(Document.id)))
    query_count = await db.execute(select(func.count(QueryLog.id)))

    vector_store = get_vector_store()
    kg = get_knowledge_graph()

    return {
        "users": user_count.scalar() or 0,
        "documents": doc_count.scalar() or 0,
        "queries": query_count.scalar() or 0,
        "vector_store": vector_store.get_stats(),
        "knowledge_graph": kg.get_stats(),
    }


@router.get("/audit-logs")
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
):
    """View audit logs (admin only)."""
    _check_admin(current_user)

    result = await db.execute(
        select(AuditLog)
        .order_by(desc(AuditLog.created_at))
        .offset(skip)
        .limit(limit)
    )
    logs = result.scalars().all()

    return {
        "logs": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details_json,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }
