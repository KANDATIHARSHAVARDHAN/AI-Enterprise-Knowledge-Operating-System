"""
EKOS Health Check Route
Verifies connectivity to all backend services.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.database import get_db
from app.db.vector_store import get_vector_store
from app.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check health of all backend services."""
    settings = get_settings()
    checks = {}

    # MySQL check
    try:
        await db.execute(text("SELECT 1"))
        checks["mysql"] = {"status": "healthy", "host": settings.mysql_host}
    except Exception as e:
        checks["mysql"] = {"status": "unhealthy", "error": str(e)}

    # FAISS check
    try:
        vs = get_vector_store()
        checks["faiss"] = {
            "status": "healthy",
            "total_vectors": vs.total_vectors,
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
        "checks": checks,
    }
