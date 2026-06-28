"""
EKOS - AI Enterprise Knowledge Operating System
FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db.database import init_db, close_db
from app.db.vector_store import get_vector_store
from app.db.knowledge_graph import get_knowledge_graph
from app.api.middleware.request_logger import RequestLoggerMiddleware
from app.api.middleware.rate_limiter import RateLimiterMiddleware
from app.api.routes import auth, documents, query, evaluation, admin, health
from app.utils.logger import logger
from app.utils.exceptions import EKOSBaseError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events."""
    # Startup
    logger.info("🚀 EKOS starting up...")
    settings = get_settings()

    # Ensure directories exist
    settings.upload_path
    settings.vector_store_dir
    settings.logs_dir

    # Initialize vector store (loads FAISS index)
    try:
        vs = get_vector_store()
        logger.info(f"✅ FAISS vector store loaded ({vs.total_vectors} vectors)")
    except Exception as e:
        logger.warning(f"⚠️ FAISS initialization warning: {e}")

    # Initialize knowledge graph
    try:
        kg = get_knowledge_graph()
        logger.info(f"✅ Knowledge graph loaded ({kg.graph.number_of_nodes()} nodes)")
    except Exception as e:
        logger.warning(f"⚠️ Knowledge graph initialization warning: {e}")

    logger.info("✅ EKOS startup complete")

    yield

    # Shutdown
    logger.info("🛑 EKOS shutting down...")
    await close_db()
    logger.info("✅ EKOS shutdown complete")


# Create FastAPI app
settings = get_settings()

app = FastAPI(
    title="EKOS - AI Enterprise Knowledge Operating System",
    description=(
        "Production-grade multi-agent RAG platform for enterprise knowledge management. "
        "Orchestrates 10 specialized AI agents to answer complex cross-source questions."
    ),
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# === Middleware ===
# Note: middleware is applied in reverse order (last added = first executed)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiter
app.add_middleware(RateLimiterMiddleware)

# Request Logger
app.add_middleware(RequestLoggerMiddleware)


# === Exception Handlers ===

@app.exception_handler(EKOSBaseError)
async def ekos_exception_handler(request: Request, exc: EKOSBaseError):
    """Handle all custom EKOS exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
        },
    )


# === Routes ===
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(query.router)
app.include_router(evaluation.router)
app.include_router(admin.router)
app.include_router(health.router)


# === Root ===

@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "name": "EKOS - AI Enterprise Knowledge Operating System",
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }
