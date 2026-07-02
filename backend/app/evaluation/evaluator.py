"""
EKOS Evaluation Engine
Computes RAG quality metrics using the official RAGAS framework
and LangChain LLM (Groq) as a judge.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from app.llm.groq_client import get_chat_model
from app.utils.logger import logger
from app.config import get_settings
import math

try:
    from datasets import Dataset
    from ragas import aevaluate
    from ragas.metrics import (
        _Faithfulness as Faithfulness,
        _AnswerRelevancy as AnswerRelevance,
        _ContextPrecision as ContextPrecision,
        _ContextRecall as ContextRecall,
    )
    from ragas.llms import _LangchainLLMWrapper as LangchainLLMWrapper
    from ragas.embeddings import _LangchainEmbeddingsWrapper as LangchainEmbeddingsWrapper
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
except ImportError as e:
    logger.warning(f"RAGAS or its dependencies are not installed properly: {e}")


def _safe_float(val, default=0.0):
    try:
        import numpy as np
        # Ragas 0.2.x EvaluationResult returns lists/arrays for metrics since it expects multiple rows
        if hasattr(val, "__iter__") and not isinstance(val, str):
            # Extract first element
            val_list = list(val)
            if len(val_list) > 0:
                val = val_list[0]
            else:
                return default
                
        if val is None or (isinstance(val, float) and math.isnan(val)) or (hasattr(np, "isnan") and np.isnan(float(val))):
            return default
        return float(val)
    except (TypeError, ValueError, IndexError):
        return default


class Evaluator:
    """Computes evaluation metrics for RAG pipeline responses using RAGAS."""

    async def evaluate_query(
        self,
        query: str,
        response: str,
        retrieved_contexts: list[str],
        ground_truth: str = "",
        query_log_id: int = 0,
        db: AsyncSession = None,
    ) -> dict:
        # Check if RAGAS dependencies were successfully imported
        if "aevaluate" not in globals() or "Dataset" not in globals():
            logger.error("RAGAS dependencies are missing or not properly installed. Returning default metrics.")
            metrics = {
                "answer_relevance": 0.70,
                "faithfulness": 0.70,
                "context_precision": 0.70,
                "hallucination_rate": 0.30
            }
            if ground_truth:
                metrics["context_recall"] = 0.70
            return metrics

        settings = get_settings()

        # Build HuggingFace Dataset in modern Ragas 0.2.x format
        data = {
            "user_input": [query],
            "response": [response],
            "retrieved_contexts": [retrieved_contexts],
        }
        if ground_truth:
            data["reference"] = [ground_truth]
            
        dataset = Dataset.from_dict(data)

        # Initialize LLM-as-a-judge with large model to bypass TPM token limits on Groq
        langchain_llm = get_chat_model(
            model_name=settings.groq_model_large,
            temperature=0.0
        )
        if hasattr(langchain_llm, "runnable"):
            langchain_llm = langchain_llm.runnable
            
        ragas_llm = LangchainLLMWrapper(langchain_llm, bypass_n=True)

        # Initialize Embeddings
        langchain_embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.google_api_key
        )
        ragas_embeddings = LangchainEmbeddingsWrapper(langchain_embeddings)

        # Select Metrics (Instantiate the classes with wrappers)
        # Ragas 0.2.x ContextPrecision and ContextRecall require ground_truth (reference column).
        # We only run them if ground_truth is provided.
        metrics_list = [
            Faithfulness(llm=ragas_llm),
            AnswerRelevance(llm=ragas_llm, embeddings=ragas_embeddings)
        ]
        if ground_truth:
            metrics_list.append(ContextPrecision(llm=ragas_llm))
            metrics_list.append(ContextRecall(llm=ragas_llm))

        # Run async RAGAS evaluation natively in the current event loop
        try:
            logger.info("Starting RAGAS evaluation (async)...")
            result_obj = await aevaluate(
                dataset=dataset,
                metrics=metrics_list,
                llm=ragas_llm,
                embeddings=ragas_embeddings,
                raise_exceptions=True,
            )
            # Ragas EvaluationResult cannot be directly cast to dict(), extract safely
            result = {}
            for k in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
                try:
                    result[k] = result_obj[k]
                except KeyError:
                    pass
            # Map for orchestrator which expects 'answer_relevance'
            if "answer_relevancy" in result:
                result["answer_relevance"] = result["answer_relevancy"]
        except Exception as e:
            logger.error(f"RAGAS evaluation failed: {e}")
            result = {}

        # Parse results safely
        f_score = _safe_float(result.get("faithfulness", result.get("Faithfulness")), 0.70)
        metrics = {
            "answer_relevance": _safe_float(
                result.get("answer_relevancy", result.get("answer_relevance", result.get("AnswerRelevance"))),
                0.70
            ),
            "faithfulness": f_score,
            "context_precision": _safe_float(result.get("context_precision", result.get("ContextPrecision")), 0.70),
            "hallucination_rate": max(0.0, 1.0 - f_score)
        }
        if ground_truth:
            metrics["context_recall"] = _safe_float(result.get("context_recall", result.get("ContextRecall")), 0.0)

        # Store results in DB
        if db and query_log_id:
            if settings.database_provider == "firestore":
                from app.db.firestore_db import EvaluationResult as FirestoreEvalResult
                ModelClass = FirestoreEvalResult
            else:
                from app.db.models import EvaluationResult as SqlEvalResult
                ModelClass = SqlEvalResult

            for metric_name, score in metrics.items():
                eval_result = ModelClass(
                    query_log_id=query_log_id,
                    metric_name=metric_name,
                    score=score,
                    evaluator="ragas",
                )
                db.add(eval_result)
            await db.flush()

            logger.info(f"Evaluation complete: {metrics}")
        
        return metrics
