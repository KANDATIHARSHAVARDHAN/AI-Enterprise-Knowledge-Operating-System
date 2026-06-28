"""
EKOS Document Routes
Handles document upload, listing, deletion, and chunk viewing.
"""

import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.database import get_db
from app.db.models import Document, DocumentChunk, User, AuditLog
from app.api.dependencies import get_current_user
from app.ingestion.pipeline import IngestionPipeline
from app.db.vector_store import get_vector_store
from app.config import get_settings

router = APIRouter(prefix="/api/documents", tags=["Documents"])
settings = get_settings()


async def _run_ingestion(file_path: str, document_id: int):
    """Background task for document ingestion."""
    from app.db.database import async_session_factory
    pipeline = IngestionPipeline()
    vector_store = get_vector_store()

    async with async_session_factory() as db:
        try:
            await pipeline.ingest_document(file_path, document_id, db, vector_store)
            await db.commit()
        except Exception as e:
            doc = await db.get(Document, document_id)
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)
                await db.commit()


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload and ingest a document."""
    # Validate file type
    supported = IngestionPipeline.get_supported_extensions()
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in supported:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file_ext}. Supported: {', '.join(supported)}"
        )

    # Validate file size
    max_size = settings.max_file_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum: {settings.max_file_size_mb}MB"
        )

    # Save file
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    upload_path = settings.upload_path / unique_name

    with open(str(upload_path), "wb") as f:
        f.write(content)

    # Create document record
    doc = Document(
        filename=unique_name,
        original_filename=file.filename,
        file_type=file_ext.lstrip("."),
        file_size_bytes=len(content),
        file_path=str(upload_path),
        status="pending",
        uploaded_by=current_user.id,
    )
    db.add(doc)
    await db.flush()

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action="UPLOAD_DOCUMENT",
        resource_type="document",
        resource_id=str(doc.id),
        details_json={"filename": file.filename, "size": len(content)},
    ))
    await db.commit()

    # Start background ingestion
    background_tasks.add_task(_run_ingestion, str(upload_path), doc.id)

    return {
        "id": doc.id,
        "filename": file.filename,
        "status": "pending",
        "message": "Document uploaded. Ingestion started in background.",
    }


@router.get("")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
):
    """List all documents."""
    result = await db.execute(
        select(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit)
    )
    documents = result.scalars().all()

    count_result = await db.execute(select(func.count(Document.id)))
    total = count_result.scalar()

    return {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.original_filename,
                "file_type": doc.file_type,
                "file_size_bytes": doc.file_size_bytes,
                "status": doc.status,
                "chunk_count": doc.chunk_count,
                "error_message": doc.error_message,
                "uploaded_by": doc.uploaded_by,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
            for doc in documents
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get document details."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "id": doc.id,
        "filename": doc.original_filename,
        "file_type": doc.file_type,
        "file_size_bytes": doc.file_size_bytes,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "error_message": doc.error_message,
        "metadata": doc.metadata_json,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document and its chunks."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete file from disk
    try:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except OSError:
        pass

    # Delete from FAISS
    try:
        vector_store = get_vector_store()
        vector_store.delete_by_document(document_id)
    except Exception:
        pass

    # Delete from MySQL (cascades to chunks)
    await db.delete(doc)

    db.add(AuditLog(
        user_id=current_user.id,
        action="DELETE_DOCUMENT",
        resource_type="document",
        resource_id=str(document_id),
    ))
    await db.commit()

    return {"message": f"Document {document_id} deleted successfully"}


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 20,
):
    """View chunks of a document."""
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .offset(skip)
        .limit(limit)
    )
    chunks = result.scalars().all()

    return {
        "chunks": [
            {
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "token_count": chunk.token_count,
                "metadata": chunk.metadata_json,
            }
            for chunk in chunks
        ],
        "document_id": document_id,
    }
