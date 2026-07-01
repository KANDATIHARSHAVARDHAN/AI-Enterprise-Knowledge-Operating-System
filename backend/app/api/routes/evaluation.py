"""
EKOS Evaluation Routes
Provides evaluation metrics and evaluation run endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.db.database import get_db
from app.api.dependencies import get_current_user
from app.config import get_settings

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])
settings = get_settings()


def _format_ts(ts):
    """Safely format a timestamp to ISO format."""
    if ts and hasattr(ts, 'isoformat'):
        return ts.isoformat()
    elif isinstance(ts, (int, float)):
        from datetime import datetime
        return datetime.fromtimestamp(ts).isoformat()
    return None


@router.get("/metrics")
async def get_aggregate_metrics(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get aggregate evaluation metrics for the current user's queries."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()

        # Get user's query logs
        query_logs = await fs.client.collection("query_logs")\
            .where("user_id", "==", current_user.id).get()
        query_log_ids = [doc.id for doc in query_logs]

        # Aggregate evaluations
        metrics_agg = {}
        for ql_id in query_log_ids:
            evals = await fs.client.collection("evaluation_results")\
                .where("query_log_id", "==", int(ql_id)).get()
            for ev in evals:
                data = ev.to_dict()
                name = data.get("metric_name", "unknown")
                score = float(data.get("score", 0))
                if name not in metrics_agg:
                    metrics_agg[name] = {"scores": [], "count": 0}
                metrics_agg[name]["scores"].append(score)
                metrics_agg[name]["count"] += 1

        metrics = [
            {
                "metric_name": name,
                "avg_score": round(sum(v["scores"]) / len(v["scores"]), 3) if v["scores"] else 0,
                "min_score": round(min(v["scores"]), 3) if v["scores"] else 0,
                "max_score": round(max(v["scores"]), 3) if v["scores"] else 0,
                "count": v["count"],
            }
            for name, v in metrics_agg.items()
        ]

        # Query stats
        total_queries = len(query_log_ids)
        latencies = [doc.to_dict().get("latency_ms", 0) for doc in query_logs]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        successful = sum(1 for doc in query_logs if doc.to_dict().get("status") == "success")

        return {
            "metrics": metrics,
            "query_stats": {
                "total_queries": total_queries,
                "avg_latency_ms": round(avg_latency, 1),
                "successful_queries": successful,
            },
        }

    else:
        from sqlalchemy import select, func
        from app.db.models import EvaluationResult, QueryLog

        result = await db.execute(
            select(
                EvaluationResult.metric_name,
                func.avg(EvaluationResult.score).label("avg_score"),
                func.min(EvaluationResult.score).label("min_score"),
                func.max(EvaluationResult.score).label("max_score"),
                func.count(EvaluationResult.id).label("count"),
            )
            .join(QueryLog, EvaluationResult.query_log_id == QueryLog.id)
            .where(QueryLog.user_id == current_user.id)
            .group_by(EvaluationResult.metric_name)
        )
        metrics = result.all()

        query_stats = await db.execute(
            select(
                func.count(QueryLog.id).label("total_queries"),
                func.avg(QueryLog.latency_ms).label("avg_latency_ms"),
                func.sum(
                    func.IF(QueryLog.status == "success", 1, 0)
                ).label("successful_queries"),
            ).where(QueryLog.user_id == current_user.id)
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
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get evaluation results for a specific query. Ownership check applied."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        log_doc = await fs.client.collection("query_logs").document(str(query_id)).get()
        if not log_doc.exists:
            raise HTTPException(status_code=404, detail="Query not found")
        log_data = log_doc.to_dict()
        if current_user.role != "admin" and log_data.get("user_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        evals_snap = await fs.client.collection("evaluation_results")\
            .where("query_log_id", "==", query_id).get()
        if not evals_snap:
            raise HTTPException(status_code=404, detail="No evaluation results found")

        return {
            "query_id": query_id,
            "evaluations": [
                {
                    "metric_name": ev.to_dict().get("metric_name"),
                    "score": round(float(ev.to_dict().get("score", 0)), 3),
                    "evaluator": ev.to_dict().get("evaluator"),
                    "details": ev.to_dict().get("details_json"),
                    "created_at": _format_ts(ev.to_dict().get("created_at")),
                }
                for ev in evals_snap
            ],
        }

    else:
        from sqlalchemy import select
        from app.db.models import EvaluationResult, QueryLog

        log = await db.get(QueryLog, query_id)
        if not log:
            raise HTTPException(status_code=404, detail="Query not found")
        if current_user.role != "admin" and log.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

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
                    "created_at": _format_ts(e.created_at),
                }
                for e in evals
            ],
        }


@router.get("/recent")
async def get_recent_evaluations(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = 20,
):
    """Get recent evaluation results for the current user."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import FirestoreDB
        fs = FirestoreDB()
        query_snap = await fs.client.collection("query_logs")\
            .where("user_id", "==", current_user.id).get()

        # Sort and limit in memory to avoid index requirements
        docs = [(doc.id, doc.to_dict()) for doc in query_snap]
        docs.sort(key=lambda item: item[1].get("created_at", 0), reverse=True)
        paginated_docs = docs[:limit]

        entries = []
        for doc_id, data in paginated_docs:
            evals_snap = await fs.client.collection("evaluation_results")\
                .where("query_log_id", "==", int(doc_id)).get()
            metrics = {ev.to_dict().get("metric_name"): round(float(ev.to_dict().get("score", 0)), 3)
                       for ev in evals_snap}

            entries.append({
                "query_id": int(doc_id),
                "query": str(data.get("query", ""))[:200],
                "latency_ms": data.get("latency_ms"),
                "status": data.get("status"),
                "created_at": _format_ts(data.get("created_at")),
                "metrics": metrics,
            })

        return {"evaluations": entries}

    else:
        from sqlalchemy import select, desc
        from app.db.models import EvaluationResult, QueryLog

        result = await db.execute(
            select(QueryLog)
            .where(QueryLog.user_id == current_user.id)
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
                "created_at": _format_ts(log.created_at),
                "metrics": {e.metric_name: round(float(e.score), 3) for e in evals},
            })

        return {"evaluations": entries}
