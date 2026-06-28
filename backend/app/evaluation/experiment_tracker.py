"""
EKOS Experiment Tracker
Integrates with MLflow to log query executions, model versions, and evaluation metrics.
"""

from typing import Any, Optional
import mlflow
from app.config import get_settings
from app.utils.logger import logger


class ExperimentTracker:
    """Tracks and logs evaluation experiments using MLflow."""

    def __init__(self):
        self.settings = get_settings()
        self._initialized = False
        self._init_mlflow()

    def _init_mlflow(self):
        """Initialize MLflow client and set experiment."""
        try:
            mlflow.set_tracking_uri(self.settings.mlflow_tracking_uri)
            mlflow.set_experiment(self.settings.mlflow_experiment_name)
            self._initialized = True
            logger.info(f"MLflow initialized: URI={self.settings.mlflow_tracking_uri}, Experiment={self.settings.mlflow_experiment_name}")
        except Exception as e:
            logger.warning(f"MLflow initialization failed (local tracking will be disabled): {e}")
            self._initialized = False

    def log_run(
        self,
        query: str,
        response: str,
        metrics: dict[str, float],
        parameters: Optional[dict[str, Any]] = None,
        tags: Optional[dict[str, str]] = None,
    ):
        """
        Log a query evaluation run to MLflow.

        Args:
            query: The user query
            response: The system response
            metrics: Evaluation scores (relevance, faithfulness, etc.)
            parameters: Model settings or configurations
            tags: Run tags (user_id, session_id, etc.)
        """
        if not self._initialized:
            logger.debug("Skipping MLflow logging as it is not initialized.")
            return

        try:
            with mlflow.start_run():
                # Log parameters
                params = parameters or {}
                params.update({
                    "model_large": self.settings.groq_model_large,
                    "model_small": self.settings.groq_model_small,
                    "chunk_size": self.settings.chunk_size,
                    "chunk_overlap": self.settings.chunk_overlap,
                })
                mlflow.log_params(params)

                # Log metrics
                mlflow.log_metrics(metrics)

                # Log tags and attributes
                run_tags = tags or {}
                run_tags.update({
                    "query": query[:250],  # MLflow tag value length limit is 250
                    "response_preview": response[:250],
                })
                mlflow.set_tags(run_tags)

                logger.info("Successfully logged run details to MLflow.")
        except Exception as e:
            logger.error(f"Failed to log run to MLflow: {e}")


# Singleton
_experiment_tracker: Optional[ExperimentTracker] = None


def get_experiment_tracker() -> ExperimentTracker:
    """Get or create the singleton experiment tracker."""
    global _experiment_tracker
    if _experiment_tracker is None:
        _experiment_tracker = ExperimentTracker()
    return _experiment_tracker
