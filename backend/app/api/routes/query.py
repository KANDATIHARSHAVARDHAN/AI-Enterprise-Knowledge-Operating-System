"""
EKOS Query Routes
Handles question asking, streaming responses, and query history.
"""

import time
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import Optional
from app.db.database import get_db
from app.db.models import User, Conversation, Message, QueryLog, AuditLog
from app.api.dependencies import get_current_user
from app.agents.orchestrator import AgentOrchestrator
from app.security.prompt_guard import get_prompt_guard
from app.security.pii_masker import get_pii_masker
from app.utils.logger import logger

router = APIRouter(prefix="/api/query", tags=["Query"])


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


@router.post("", response_model=QueryResponse)
async def ask_question(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 20,
):
    """Get query history for the current user."""
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
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "skip": skip,
        "limit": limit,
    }


@router.get("/{query_id}/trace")
async def get_query_trace(
    query_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the agent execution trace for a specific query."""
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
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


@router.get("/conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all conversations for the current user."""
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
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            }
            for conv in conversations
        ],
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all messages in a conversation."""
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
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ],
    }
