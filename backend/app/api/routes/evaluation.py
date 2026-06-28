"""
EKOS Evaluation Routes
Provides evaluation metrics and evaluation run endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db.database import get_db
from app.db.models import User, EvaluationResult, QueryLog
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])


@router.get("/metrics")
async def get_aggregate_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregate evaluation metrics across all queries."""
    result = await db.execute(
        select(
            EvaluationResult.metric_name,
            func.avg(EvaluationResult.score).label("avg_score"),
            func.min(EvaluationResult.score).label("min_score"),
            func.max(EvaluationResult.score).label("max_score"),
            func.count(EvaluationResult.id).label("count"),
        ).group_by(EvaluationResult.metric_name)
    )
    metrics = result.all()

    # Also get overall query stats
    query_stats = await db.execute(
        select(
            func.count(QueryLog.id).label("total_queries"),
            func.avg(QueryLog.latency_ms).label("avg_latency_ms"),
            func.sum(
                func.IF(QueryLog.status == "success", 1, 0)
            ).label("successful_queries"),
        )
    )
    stats = query_stats.one_or_none()

    return {
        "metrics": [
            {
                "metric_name": m.metric_name,
                "avg_score": round(float(m.avg_score or 0), 3),
                "min_score": round(float(m.min_score or 0), 3),
                "max_score": round(float(m.max_score or 0), 3),
                "count": m.count,
            }
            for m in metrics
        ],
        "query_stats": {
            "total_queries": stats.total_queries if stats else 0,
            "avg_latency_ms": round(float(stats.avg_latency_ms or 0), 1) if stats else 0,
            "successful_queries": int(stats.successful_queries or 0) if stats else 0,
        },
    }


@router.get("/queries/{query_id}")
async def get_query_evaluation(
    query_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get evaluation results for a specific query."""
    result = await db.execute(
        select(EvaluationResult)
        .where(EvaluationResult.query_log_id == query_id)
    )
    evals = result.scalars().all()

    if not evals:
        raise HTTPException(status_code=404, detail="No evaluation results found")

    return {
        "query_id": query_id,
        "evaluations": [
            {
                "metric_name": e.metric_name,
                "score": round(float(e.score), 3),
                "evaluator": e.evaluator,
                "details": e.details_json,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in evals
        ],
    }


@router.get("/recent")
async def get_recent_evaluations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 20,
):
    """Get recent evaluation results with query info."""
    result = await db.execute(
        select(QueryLog)
        .order_by(desc(QueryLog.created_at))
        .limit(limit)
    )
    logs = result.scalars().all()

    entries = []
    for log in logs:
        eval_result = await db.execute(
            select(EvaluationResult)
            .where(EvaluationResult.query_log_id == log.id)
        )
        evals = eval_result.scalars().all()

        entries.append({
            "query_id": log.id,
            "query": log.query[:200],
            "latency_ms": log.latency_ms,
            "status": log.status,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "metrics": {e.metric_name: round(float(e.score), 3) for e in evals},
        })

    return {"evaluations": entries}
