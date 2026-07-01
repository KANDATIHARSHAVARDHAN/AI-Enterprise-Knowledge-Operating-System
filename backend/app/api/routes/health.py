"""
EKOS Health Check Route
Verifies connectivity to all backend services.
"""

from fastapi import APIRouter, Depends
from app.db.database import get_db
from app.db.vector_store import get_vector_store
from app.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/api/health")
async def health_check(db=Depends(get_db)):
    """Check health of all backend services."""
    settings = get_settings()
    checks = {}

    # Database check (MySQL or Firestore)
    try:
        if settings.database_provider == "firestore":
            from app.db.firestore_db import get_firestore_client
            client = get_firestore_client()
            if client is None:
                raise ValueError("Firestore client could not be initialized (invalid or missing credentials)")
            checks["database"] = {
                "status": "healthy",
                "provider": "firestore",
                "project": settings.firebase_project_id,
            }
        else:
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
            checks["database"] = {
                "status": "healthy",
                "provider": "mysql",
                "host": settings.mysql_host,
            }
    except Exception as e:
        checks["database"] = {
            "status": "unhealthy",
            "provider": settings.database_provider,
            "error": str(e),
        }

    # FAISS check
    try:
        vs = get_vector_store()
        checks["faiss"] = {
            "status": "healthy",
            "total_vectors": vs.total_vectors,
            "cloud_sync": settings.database_provider == "firestore",
        }
    except Exception as e:
        checks["faiss"] = {"status": "unhealthy", "error": str(e)}

    # Groq API check
    try:
        from app.llm.groq_client import get_groq_client
        get_groq_client()
        checks["groq"] = {
            "status": "healthy" if settings.groq_api_key else "unconfigured",
        }
    except Exception as e:
        checks["groq"] = {"status": "unhealthy", "error": str(e)}

    # Google Embeddings check
    checks["embeddings"] = {
        "status": "healthy" if settings.google_api_key else "unconfigured",
        "model": settings.embedding_model,
    }

    overall = "healthy" if all(
        c.get("status") == "healthy" for c in checks.values()
    ) else "degraded"

    return {
        "status": overall,
        "version": settings.app_version,
        "environment": "production" if settings.database_provider == "firestore" else "development",
        "checks": checks,
    }
