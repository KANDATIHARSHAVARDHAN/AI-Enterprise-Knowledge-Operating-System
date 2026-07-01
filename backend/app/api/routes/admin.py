"""
EKOS Admin Routes
User management, system stats, and audit logs.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.db.database import get_db
from app.api.dependencies import get_current_user
from app.db.vector_store import get_vector_store
from app.db.knowledge_graph import get_knowledge_graph
from app.config import get_settings

router = APIRouter(prefix="/api/admin", tags=["Admin"])
settings = get_settings()


def _check_admin(user):
    """Verify user has admin role."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


class UpdateRoleRequest(BaseModel):
    role: str


@router.get("/users")
async def list_users(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all users (admin only)."""
    _check_admin(current_user)

    def _format_ts(ts):
        if ts and hasattr(ts, 'isoformat'):
            return ts.isoformat()
        elif isinstance(ts, (int, float)):
            from datetime import datetime
            return datetime.fromtimestamp(ts).isoformat()
        return None

    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        users_ref = fs.client.collection("users")
        docs = await users_ref.get()
        from app.db.firestore_db import User
        users = [User(**doc.to_dict()) for doc in docs]
    else:
        from sqlalchemy import select
        from app.db.models import User
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
                "created_at": _format_ts(u.created_at),
            }
            for u in users
        ],
    }


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    request: UpdateRoleRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update a user's role (admin only)."""
    _check_admin(current_user)

    if request.role not in ["admin", "analyst", "viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        user = await fs.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await fs.client.collection("users").document(str(user_id)).update({"role": request.role})
        await fs.create_audit_log({
            "user_id": current_user.id,
            "action": "UPDATE_ROLE",
            "resource_type": "user",
            "resource_id": str(user_id),
            "details_json": {"new_role": request.role},
        })
    else:
        from app.db.models import User, AuditLog
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
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a user (admin only)."""
    _check_admin(current_user)

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        user = await fs.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await fs.client.collection("users").document(str(user_id)).delete()
        await fs.create_audit_log({
            "user_id": current_user.id,
            "action": "DELETE_USER",
            "resource_type": "user",
            "resource_id": str(user_id),
        })
    else:
        from app.db.models import User, AuditLog
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
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get system-wide statistics."""
    _check_admin(current_user)

    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        users = await fs.client.collection("users").get()
        docs = await fs.client.collection("documents").get()
        logs = await fs.client.collection("query_logs").get()
        user_count = len(users)
        doc_count = len(docs)
        query_count = len(logs)
    else:
        from sqlalchemy import select, func
        from app.db.models import User, Document, QueryLog
        user_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
        doc_count = (await db.execute(select(func.count(Document.id)))).scalar() or 0
        query_count = (await db.execute(select(func.count(QueryLog.id)))).scalar() or 0

    vector_store = get_vector_store()
    kg = get_knowledge_graph()

    return {
        "users": user_count,
        "documents": doc_count,
        "queries": query_count,
        "vector_store": vector_store.get_stats(),
        "knowledge_graph": kg.get_stats(),
    }


@router.get("/audit-logs")
async def get_audit_logs(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
):
    """View audit logs (admin only)."""
    _check_admin(current_user)

    def _format_ts(ts):
        if ts and hasattr(ts, 'isoformat'):
            return ts.isoformat()
        elif isinstance(ts, (int, float)):
            from datetime import datetime
            return datetime.fromtimestamp(ts).isoformat()
        return None

    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB, AuditLog
        from google.cloud import firestore
        fs = FirestoreDB()
        query = fs.client.collection("audit_logs").order_by(
            "created_at", direction=firestore.Query.DESCENDING
        ).offset(skip).limit(limit)
        docs = await query.get()
        logs = [AuditLog(**doc.to_dict()) for doc in docs]
    else:
        from sqlalchemy import select, desc
        from app.db.models import AuditLog
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
                "details": getattr(log, 'details_json', None),
                "created_at": _format_ts(log.created_at),
            }
            for log in logs
        ],
    }


@router.get("/dashboard-data")
async def get_dashboard_chart_data(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get real dashboard chart data from the machine_events table.
    Returns machine failure aggregations and severity distribution.
    In Firestore mode, uses the SQLite-seeded enterprise data.
    """
    if settings.database_provider == "firestore":
        # Use the SQL agent's SQLite connection for enterprise data queries
        from app.agents.sql_agent import _get_sqlite_connection
        conn = _get_sqlite_connection()

        cursor = conn.execute("""
            SELECT machine_name,
                   COUNT(*) as failures,
                   COALESCE(SUM(cost_usd), 0) as cost,
                   COALESCE(SUM(downtime_hours), 0) as downtime
            FROM machine_events
            WHERE event_type = 'failure'
            GROUP BY machine_name
            ORDER BY COUNT(*) DESC
        """)
        machine_data = [
            {"name": row[0], "failures": row[1], "cost": float(row[2]), "downtime": float(row[3])}
            for row in cursor.fetchall()
        ]

        cursor = conn.execute("""
            SELECT severity, COUNT(*) as value
            FROM machine_events
            GROUP BY severity
        """)
        severity_colors = {
            "critical": "#f87171",
            "high": "#fb923c",
            "medium": "#fbbf24",
            "low": "#38bdf8",
        }
        severity_data = [
            {
                "name": row[0].capitalize() if row[0] else "Unknown",
                "value": row[1],
                "color": severity_colors.get(row[0], "#94a3b8"),
            }
            for row in cursor.fetchall()
        ]
    else:
        from sqlalchemy import select, func, desc
        from app.db.models import MachineEvent

        machine_result = await db.execute(
            select(
                MachineEvent.machine_name,
                func.count(MachineEvent.id).label("failures"),
                func.sum(MachineEvent.cost_usd).label("cost"),
                func.sum(MachineEvent.downtime_hours).label("downtime"),
            )
            .where(MachineEvent.event_type == "failure")
            .group_by(MachineEvent.machine_name)
            .order_by(desc(func.count(MachineEvent.id)))
        )
        machine_data = [
            {
                "name": row.machine_name,
                "failures": row.failures,
                "cost": float(row.cost or 0),
                "downtime": float(row.downtime or 0),
            }
            for row in machine_result.all()
        ]

        severity_result = await db.execute(
            select(
                MachineEvent.severity,
                func.count(MachineEvent.id).label("value"),
            )
            .group_by(MachineEvent.severity)
        )
        severity_colors = {
            "critical": "#f87171",
            "high": "#fb923c",
            "medium": "#fbbf24",
            "low": "#38bdf8",
        }
        severity_data = [
            {
                "name": row.severity.capitalize() if row.severity else "Unknown",
                "value": row.value,
                "color": severity_colors.get(row.severity, "#94a3b8"),
            }
            for row in severity_result.all()
        ]

    return {
        "machine_failure_data": machine_data,
        "severity_data": severity_data,
    }
