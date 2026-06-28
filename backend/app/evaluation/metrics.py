"""
EKOS Evaluation Metrics
Defines validation schemas and thresholds for evaluation metrics.
"""

from typing import Optional
from pydantic import BaseModel, Field

class MetricThresholds:
    """Standard evaluation quality thresholds."""
    ANSWER_RELEVANCE = 0.7
    FAITHFULNESS = 0.8
    CONTEXT_PRECISION = 0.7
    CONTEXT_RECALL = 0.7
    LATENCY_THRESHOLD_MS = 10000.0  # 10s maximum expected


class EvaluationScore(BaseModel):
    """Schema for individual metric scores."""
    metric_name: str
    score: float = Field(..., ge=0.0, le=1.0)
    passed: bool
    reason: str = ""


class QueryEvaluationSummary(BaseModel):
    """Summary of all evaluation metrics for a query."""
    query_id: int
    answer_relevance: float
    faithfulness: float
    context_precision: float
    context_recall: Optional[float] = None
    hallucination_rate: float
    passed_all: bool
    latency_ms: int
