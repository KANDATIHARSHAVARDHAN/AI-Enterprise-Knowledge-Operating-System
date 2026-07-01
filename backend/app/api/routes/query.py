"""
EKOS Query Routes
Handles question asking, streaming responses, and query history.
"""

import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.db.database import get_db
from app.api.dependencies import get_current_user
from app.agents.orchestrator import AgentOrchestrator
from app.security.prompt_guard import get_prompt_guard
from app.security.pii_masker import get_pii_masker
from app.config import get_settings
from app.utils.logger import logger

router = APIRouter(prefix="/api/query", tags=["Query"])
settings = get_settings()


class QueryRequest(BaseModel):
    query: str
    conversation_id: Optional[int] = None


class QueryResponse(BaseModel):
    response: str
    confidence_score: float
    citations: list
    agent_trace: list
    latency_ms: int
    conversation_id: int
    message_id: int


def _format_ts(ts):
    """Safely format a timestamp to ISO format."""
    if ts and hasattr(ts, 'isoformat'):
        return ts.isoformat()
    elif isinstance(ts, (int, float)):
        from datetime import datetime
        return datetime.fromtimestamp(ts).isoformat()
    return None


@router.post("", response_model=QueryResponse)
async def ask_question(
    request: QueryRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Ask a question using the multi-agent system."""
    start_time = time.time()

    # Prompt injection check
    prompt_guard = get_prompt_guard()
    is_safe, reason = prompt_guard.check(request.query)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Query blocked: {reason}")

    # PII masking
    pii_masker = get_pii_masker()
    masked_query, pii_found = pii_masker.mask(request.query)
    if pii_found:
        logger.info(f"PII masked in query: {len(pii_found)} items")

    if settings.database_provider == "firestore":
        return await _ask_firestore(request, current_user, masked_query, start_time, db)
    else:
        return await _ask_mysql(request, current_user, masked_query, start_time, db)


async def _ask_firestore(request, current_user, masked_query, start_time, db):
    """Handle question asking with Firestore backend."""
    from app.db.firestore_db import FirestoreDB
    fs = FirestoreDB()

    # Get or create conversation
    conversation_id = request.conversation_id
    if not conversation_id:
        conv = await fs.create_conversation({
            "user_id": current_user.id,
            "title": request.query[:100],
        })
        conversation_id = conv.id
    else:
        conv = await fs.get_conversation(conversation_id)
        if not conv or conv.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # Save user message
    user_msg = await fs.create_message({
        "conversation_id": conversation_id,
        "role": "user",
        "content": request.query,
    })

    # Run multi-agent orchestration
    orchestrator = AgentOrchestrator(db_session=db)
    result = await orchestrator.run(
        query=masked_query,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )

    latency_ms = int((time.time() - start_time) * 1000)

    # Save assistant message
    assistant_msg = await fs.create_message({
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": result.get("response", ""),
        "agent_trace_json": result.get("agent_trace", []),
        "citations_json": result.get("citations", []),
        "confidence_score": result.get("confidence_score", 0),
        "latency_ms": latency_ms,
    })

    # Save query log
    await fs.create_query_log({
        "user_id": current_user.id,
        "conversation_id": conversation_id,
        "query": request.query,
        "response_summary": result.get("response", "")[:500],
        "agent_path_json": result.get("agent_trace", []),
        "latency_ms": latency_ms,
        "model_used": "groq",
        "status": "success" if not result.get("error") else "failed",
        "error_message": result.get("error"),
    })

    # Audit log
    await fs.create_audit_log({
        "user_id": current_user.id,
        "action": "QUERY",
        "resource_type": "query",
        "details_json": {"query": request.query[:200], "latency_ms": latency_ms},
    })

    return QueryResponse(
        response=result.get("response", ""),
        confidence_score=result.get("confidence_score", 0),
        citations=result.get("citations", []),
        agent_trace=result.get("agent_trace", []),
        latency_ms=latency_ms,
        conversation_id=conversation_id,
        message_id=assistant_msg.id,
    )


async def _ask_mysql(request, current_user, masked_query, start_time, db):
    """Handle question asking with MySQL backend."""
    from app.db.models import Conversation, Message, QueryLog, AuditLog

    # Get or create conversation
    conversation_id = request.conversation_id
    if not conversation_id:
        conversation = Conversation(
            user_id=current_user.id,
            title=request.query[:100],
        )
        db.add(conversation)
        await db.flush()
        conversation_id = conversation.id
    else:
        conv = await db.get(Conversation, conversation_id)
        if not conv or conv.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # Save user message
    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=request.query,
    )
    db.add(user_message)
    await db.flush()

    # Run multi-agent orchestration
    orchestrator = AgentOrchestrator(db_session=db)
    result = await orchestrator.run(
        query=masked_query,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )

    latency_ms = int((time.time() - start_time) * 1000)

    # Save assistant message
    assistant_message = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=result.get("response", ""),
        agent_trace_json=result.get("agent_trace", []),
        citations_json=result.get("citations", []),
        confidence_score=result.get("confidence_score", 0),
        latency_ms=latency_ms,
    )
    db.add(assistant_message)

    # Save query log
    query_log = QueryLog(
        user_id=current_user.id,
        conversation_id=conversation_id,
        query=request.query,
        response_summary=result.get("response", "")[:500],
        agent_path_json=result.get("agent_trace", []),
        latency_ms=latency_ms,
        model_used="groq",
        status="success" if not result.get("error") else "failed",
        error_message=result.get("error"),
    )
    db.add(query_log)

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action="QUERY",
        resource_type="query",
        details_json={"query": request.query[:200], "latency_ms": latency_ms},
    ))

    await db.commit()

    return QueryResponse(
        response=result.get("response", ""),
        confidence_score=result.get("confidence_score", 0),
        citations=result.get("citations", []),
        agent_trace=result.get("agent_trace", []),
        latency_ms=latency_ms,
        conversation_id=conversation_id,
        message_id=assistant_message.id,
    )


@router.get("/history")
async def get_query_history(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = 0,
    limit: int = 20,
):
    """Get query history for the current user."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        query_snap = await fs.client.collection("query_logs")\
            .where("user_id", "==", current_user.id).get()

        # Sort and paginate in memory to avoid index requirements
        docs = [(doc.id, doc.to_dict()) for doc in query_snap]
        docs.sort(key=lambda item: item[1].get("created_at", 0), reverse=True)
        paginated_docs = docs[skip:skip+limit]

        return {
            "queries": [
                {
                    "id": int(doc_id),
                    "query": doc_dict.get("query", ""),
                    "response_summary": doc_dict.get("response_summary", ""),
                    "latency_ms": doc_dict.get("latency_ms"),
                    "status": doc_dict.get("status"),
                    "created_at": _format_ts(doc_dict.get("created_at")),
                }
                for doc_id, doc_dict in paginated_docs
            ],
            "skip": skip,
            "limit": limit,
        }
    else:
        from sqlalchemy import select, desc
        from app.db.models import QueryLog
        result = await db.execute(
            select(QueryLog)
            .where(QueryLog.user_id == current_user.id)
            .order_by(desc(QueryLog.created_at))
            .offset(skip)
            .limit(limit)
        )
        logs = result.scalars().all()

        return {
            "queries": [
                {
                    "id": log.id,
                    "query": log.query,
                    "response_summary": log.response_summary,
                    "latency_ms": log.latency_ms,
                    "status": log.status,
                    "created_at": _format_ts(log.created_at),
                }
                for log in logs
            ],
            "skip": skip,
            "limit": limit,
        }


@router.get("/{query_id}/trace")
async def get_query_trace(
    query_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get the agent execution trace for a specific query."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        doc = await fs.client.collection("query_logs").document(str(query_id)).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Query not found")
        data = doc.to_dict()
        return {
            "id": query_id,
            "query": data.get("query", ""),
            "response_summary": data.get("response_summary", ""),
            "agent_trace": data.get("agent_path_json", []),
            "latency_ms": data.get("latency_ms"),
            "status": data.get("status"),
            "model_used": data.get("model_used"),
            "created_at": _format_ts(data.get("created_at")),
        }
    else:
        from app.db.models import QueryLog
        log = await db.get(QueryLog, query_id)
        if not log:
            raise HTTPException(status_code=404, detail="Query not found")
        return {
            "id": log.id,
            "query": log.query,
            "response_summary": log.response_summary,
            "agent_trace": log.agent_path_json or [],
            "latency_ms": log.latency_ms,
            "status": log.status,
            "model_used": log.model_used,
            "created_at": _format_ts(log.created_at),
        }


@router.get("/conversations")
async def list_conversations(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all conversations for the current user."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        snap = await fs.client.collection("conversations")\
            .where("user_id", "==", current_user.id).get()

        # Sort and limit in memory
        docs = [(doc.id, doc.to_dict()) for doc in snap]
        docs.sort(key=lambda item: item[1].get("updated_at", 0), reverse=True)
        paginated_docs = docs[:50]

        return {
            "conversations": [
                {
                    "id": int(doc_id),
                    "title": doc_dict.get("title", ""),
                    "created_at": _format_ts(doc_dict.get("created_at")),
                    "updated_at": _format_ts(doc_dict.get("updated_at")),
                }
                for doc_id, doc_dict in paginated_docs
            ],
        }
    else:
        from sqlalchemy import select, desc
        from app.db.models import Conversation
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == current_user.id)
            .order_by(desc(Conversation.updated_at))
            .limit(50)
        )
        conversations = result.scalars().all()

        return {
            "conversations": [
                {
                    "id": conv.id,
                    "title": conv.title,
                    "created_at": _format_ts(conv.created_at),
                    "updated_at": _format_ts(conv.updated_at),
                }
                for conv in conversations
            ],
        }


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all messages in a conversation."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        conv = await fs.get_conversation(conversation_id)
        if not conv or conv.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")

        msgs_snap = await fs.client.collection("messages")\
            .where("conversation_id", "==", conversation_id).get()

        # Sort in memory
        docs = [(doc.id, doc.to_dict()) for doc in msgs_snap]
        docs.sort(key=lambda item: item[1].get("created_at", 0))

        return {
            "conversation_id": conversation_id,
            "title": conv.title,
            "messages": [
                {
                    "id": int(doc_id),
                    "role": doc_dict.get("role"),
                    "content": doc_dict.get("content", ""),
                    "agent_trace": doc_dict.get("agent_trace_json"),
                    "citations": doc_dict.get("citations_json"),
                    "confidence_score": doc_dict.get("confidence_score"),
                    "latency_ms": doc_dict.get("latency_ms"),
                    "created_at": _format_ts(doc_dict.get("created_at")),
                }
                for doc_id, doc_dict in docs
            ],
        }
    else:
        from sqlalchemy import select
        from app.db.models import Conversation, Message
        conv = await db.get(Conversation, conversation_id)
        if not conv or conv.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")

        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        return {
            "conversation_id": conversation_id,
            "title": conv.title,
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "agent_trace": msg.agent_trace_json,
                    "citations": msg.citations_json,
                    "confidence_score": msg.confidence_score,
                    "latency_ms": msg.latency_ms,
                    "created_at": _format_ts(msg.created_at),
                }
                for msg in messages
            ],
        }


@router.get("/dashboard-stats")
async def get_dashboard_stats(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get per-user dashboard statistics.
    Returns the current user's document count, query count, and recent query history.
    """
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        docs = await fs.client.collection("documents")\
            .where("uploaded_by", "==", current_user.id).get()
        queries = await fs.client.collection("query_logs")\
            .where("user_id", "==", current_user.id).get()
        convs = await fs.client.collection("conversations")\
            .where("user_id", "==", current_user.id).get()

        latencies = [d.to_dict().get("latency_ms", 0) for d in queries]
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        total_chunks = sum(int(d.to_dict().get("chunk_count", 0)) for d in docs)

        return {
            "user_id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "documents": len(docs),
            "queries": len(queries),
            "conversations": len(convs),
            "vector_count": total_chunks,
            "avg_latency_ms": round(avg_lat, 1),
        }
    else:
        from sqlalchemy import select, func
        from app.db.models import Document, QueryLog, Conversation, DocumentChunk

        doc_count = (await db.execute(
            select(func.count(Document.id)).where(Document.uploaded_by == current_user.id)
        )).scalar() or 0

        query_count = (await db.execute(
            select(func.count(QueryLog.id)).where(QueryLog.user_id == current_user.id)
        )).scalar() or 0

        conv_count = (await db.execute(
            select(func.count(Conversation.id)).where(Conversation.user_id == current_user.id)
        )).scalar() or 0

        chunk_count = (await db.execute(
            select(func.count(DocumentChunk.id))
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.uploaded_by == current_user.id)
        )).scalar() or 0

        avg_latency = (await db.execute(
            select(func.avg(QueryLog.latency_ms)).where(QueryLog.user_id == current_user.id)
        )).scalar() or 0

        return {
            "user_id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "documents": doc_count,
            "queries": query_count,
            "conversations": conv_count,
            "vector_count": chunk_count,
            "avg_latency_ms": round(float(avg_latency), 1),
        }


@router.get("/document-analytics")
async def get_document_analytics(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get document-driven analytics for the dashboard charts.
    Returns file type distribution, status breakdown, upload timeline,
    and top documents by chunk count.
    """
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        if current_user.role == "admin":
            docs_snap = await fs.client.collection("documents").get()
        else:
            docs_snap = await fs.client.collection("documents")\
                .where("uploaded_by", "==", current_user.id).get()

        docs = [d.to_dict() for d in docs_snap]

        # File type distribution
        ft_counts = {}
        for d in docs:
            ft = (d.get("file_type") or "unknown").upper()
            if ft not in ft_counts:
                ft_counts[ft] = {"count": 0, "total_size": 0}
            ft_counts[ft]["count"] += 1
            ft_counts[ft]["total_size"] += d.get("file_size_bytes", 0)
        file_type_data = [
            {"name": k, "count": v["count"], "total_size": v["total_size"]}
            for k, v in ft_counts.items()
        ]

        # Status breakdown
        status_counts = {}
        for d in docs:
            s = d.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1
        status_colors = {
            "completed": "#22d3ee", "processing": "#fbbf24",
            "pending": "#94a3b8", "failed": "#f87171",
        }
        status_data = [
            {"name": k.capitalize(), "value": v, "color": status_colors.get(k, "#64748b")}
            for k, v in status_counts.items()
        ]

        # Top docs by chunk count
        sorted_docs = sorted(docs, key=lambda x: x.get("chunk_count", 0), reverse=True)[:10]
        top_docs_data = [
            {
                "name": (d.get("original_filename") or "")[:25],
                "chunks": d.get("chunk_count", 0),
                "size_kb": round(d.get("file_size_bytes", 0) / 1024, 1),
                "file_type": (d.get("file_type") or "").upper(),
            }
            for d in sorted_docs if d.get("chunk_count", 0) > 0
        ]

        return {
            "file_type_data": file_type_data,
            "status_data": status_data,
            "upload_timeline": [],
            "top_docs_data": top_docs_data,
        }

    else:
        from sqlalchemy import select, func, desc
        from app.db.models import Document, DocumentChunk

        ownership_filter = (
            True if current_user.role == "admin"
            else (Document.uploaded_by == current_user.id)
        )

        file_type_result = await db.execute(
            select(
                Document.file_type,
                func.count(Document.id).label("count"),
                func.coalesce(func.sum(Document.file_size_bytes), 0).label("total_size"),
            )
            .where(ownership_filter)
            .group_by(Document.file_type)
            .order_by(desc(func.count(Document.id)))
        )
        file_type_data = [
            {"name": row.file_type.upper() if row.file_type else "UNKNOWN",
             "count": row.count, "total_size": int(row.total_size)}
            for row in file_type_result.all()
        ]

        status_result = await db.execute(
            select(Document.status, func.count(Document.id).label("value"))
            .where(ownership_filter).group_by(Document.status)
        )
        status_colors = {
            "completed": "#22d3ee", "processing": "#fbbf24",
            "pending": "#94a3b8", "failed": "#f87171",
        }
        status_data = [
            {"name": (row.status or "unknown").capitalize(), "value": row.value,
             "color": status_colors.get(row.status, "#64748b")}
            for row in status_result.all()
        ]

        timeline_result = await db.execute(
            select(
                func.date(Document.created_at).label("upload_date"),
                func.count(Document.id).label("count"),
                func.coalesce(func.sum(Document.chunk_count), 0).label("chunks"),
            )
            .where(ownership_filter)
            .group_by(func.date(Document.created_at))
            .order_by(func.date(Document.created_at))
        )
        upload_timeline = [
            {"date": str(row.upload_date) if row.upload_date else "",
             "documents": row.count, "chunks": int(row.chunks)}
            for row in timeline_result.all()
        ]

        top_docs_result = await db.execute(
            select(Document.original_filename, Document.file_type,
                   Document.chunk_count, Document.file_size_bytes)
            .where(ownership_filter)
            .where(Document.status == "completed")
            .where(Document.chunk_count > 0)
            .order_by(desc(Document.chunk_count))
            .limit(10)
        )
        top_docs_data = [
            {
                "name": (row.original_filename[:25] + "..."
                         if len(row.original_filename or "") > 25
                         else row.original_filename),
                "chunks": row.chunk_count or 0,
                "size_kb": round((row.file_size_bytes or 0) / 1024, 1),
                "file_type": (row.file_type or "").upper(),
            }
            for row in top_docs_result.all()
        ]

        return {
            "file_type_data": file_type_data,
            "status_data": status_data,
            "upload_timeline": upload_timeline,
            "top_docs_data": top_docs_data,
        }
