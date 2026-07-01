"""
EKOS Document Routes
Handles document upload, listing, deletion, and chunk viewing.
"""

import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from app.db.database import get_db
from app.api.dependencies import get_current_user
from app.ingestion.pipeline import IngestionPipeline
from app.db.vector_store import get_vector_store
from app.config import get_settings

router = APIRouter(prefix="/api/documents", tags=["Documents"])
settings = get_settings()


async def _run_ingestion(file_path: str, document_id: int):
    """Background task for document ingestion."""
    import traceback
    from app.utils.logger import logger

    pipeline = IngestionPipeline()
    vector_store = get_vector_store()

    if settings.database_provider == "firestore":
        from app.db.firestore_db import AsyncFirestoreSession
        db = AsyncFirestoreSession()
        try:
            result = await pipeline.ingest_document(
                file_path, document_id, db, vector_store
            )
            logger.info(
                f"Ingestion completed for document {document_id}: "
                f"{result.get('chunk_count', 0)} chunks"
            )
        except Exception as e:
            logger.error(
                f"Background ingestion failed for document {document_id}: {e}\n"
                f"{traceback.format_exc()}"
            )
    else:
        from app.db.database import async_session_factory
        async with async_session_factory() as db:
            try:
                result = await pipeline.ingest_document(
                    file_path, document_id, db, vector_store
                )
                logger.info(
                    f"Ingestion completed for document {document_id}: "
                    f"{result.get('chunk_count', 0)} chunks"
                )
            except Exception as e:
                logger.error(
                    f"Background ingestion failed for document {document_id}: {e}\n"
                    f"{traceback.format_exc()}"
                )


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
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

    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        doc = await fs.create_document({
            "filename": unique_name,
            "original_filename": file.filename,
            "file_type": file_ext.lstrip("."),
            "file_size_bytes": len(content),
            "file_path": str(upload_path),
            "status": "pending",
            "uploaded_by": current_user.id,
        })
        await fs.create_audit_log({
            "user_id": current_user.id,
            "action": "UPLOAD_DOCUMENT",
            "resource_type": "document",
            "resource_id": str(doc.id),
            "details_json": {"filename": file.filename, "size": len(content)},
        })
    else:
        from app.db.models import Document, AuditLog
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
    db=Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
):
    """List documents. Non-admin users see only their own documents."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        if current_user.role != "admin":
            docs = await fs.get_documents(uploaded_by=current_user.id)
        else:
            docs = await fs.get_documents()
        total = len(docs)
        docs = docs[skip:skip + limit]
    else:
        from sqlalchemy import select, func
        from app.db.models import Document
        query = select(Document).order_by(Document.created_at.desc())
        count_query = select(func.count(Document.id))
        if current_user.role != "admin":
            query = query.where(Document.uploaded_by == current_user.id)
            count_query = count_query.where(Document.uploaded_by == current_user.id)
        result = await db.execute(query.offset(skip).limit(limit))
        docs = result.scalars().all()
        count_result = await db.execute(count_query)
        total = count_result.scalar()

    def _format_ts(ts):
        if ts and hasattr(ts, 'isoformat'):
            return ts.isoformat()
        elif isinstance(ts, (int, float)):
            from datetime import datetime
            return datetime.fromtimestamp(ts).isoformat()
        return None

    return {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.original_filename,
                "file_type": doc.file_type,
                "file_size_bytes": doc.file_size_bytes,
                "status": doc.status,
                "chunk_count": doc.chunk_count,
                "error_message": getattr(doc, 'error_message', None),
                "uploaded_by": doc.uploaded_by,
                "created_at": _format_ts(doc.created_at),
            }
            for doc in docs
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get document details. Ownership check for non-admin users."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        doc = await fs.get_document(document_id)
    else:
        from app.db.models import Document
        doc = await db.get(Document, document_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if current_user.role != "admin" and doc.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    def _format_ts(ts):
        if ts and hasattr(ts, 'isoformat'):
            return ts.isoformat()
        elif isinstance(ts, (int, float)):
            from datetime import datetime
            return datetime.fromtimestamp(ts).isoformat()
        return None

    return {
        "id": doc.id,
        "filename": doc.original_filename,
        "file_type": doc.file_type,
        "file_size_bytes": doc.file_size_bytes,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "error_message": getattr(doc, 'error_message', None),
        "metadata": getattr(doc, 'metadata_json', None),
        "created_at": _format_ts(doc.created_at),
    }


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a document and its chunks. Ownership check for non-admin users."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        doc = await fs.get_document(document_id)
    else:
        from app.db.models import Document, AuditLog
        doc = await db.get(Document, document_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if current_user.role != "admin" and doc.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

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

    # Delete from database
    if settings.database_provider == "firestore":
        await fs.delete_document(document_id)
        await fs.create_audit_log({
            "user_id": current_user.id,
            "action": "DELETE_DOCUMENT",
            "resource_type": "document",
            "resource_id": str(document_id),
        })
    else:
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
    db=Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = 0,
):
    """View chunks of a document. Ownership check for non-admin users."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        doc = await fs.get_document(document_id)
    else:
        from app.db.models import Document, DocumentChunk
        doc = await db.get(Document, document_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if current_user.role != "admin" and doc.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    limit = 20
    if settings.database_provider == "firestore":
        all_chunks = await fs.get_chunks(document_id)
        chunks = all_chunks[skip:skip + limit]
    else:
        from sqlalchemy import select
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
                "metadata": getattr(chunk, 'metadata_json', None),
            }
            for chunk in chunks
        ],
        "document_id": document_id,
    }
