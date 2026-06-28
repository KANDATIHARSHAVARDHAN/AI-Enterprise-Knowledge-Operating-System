"""
EKOS Cross-Encoder Reranker
Reranks retrieved results using a cross-encoder model for better precision.
"""

from app.utils.logger import logger


class Reranker:
    """Cross-encoder based reranker for improving retrieval precision."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """Lazy load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name)
                logger.info(f"Loaded reranker model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to load reranker model: {e}. Using score-based fallback.")
                self._model = None

    def rerank(
        self,
        query: str,
        results: list[dict],
        top_k: int = 5,
    ) -> list[dict]:
        """
        Rerank retrieved results using cross-encoder.

        Args:
            query: Original search query
            results: List of retrieved results with metadata
            top_k: Number of reranked results to return

        Returns:
            Reranked list of results
        """
        if not results:
            return []

        self._load_model()

        if self._model is None:
            # Fallback: return top-k by original score
            return results[:top_k]

        try:
            # Prepare query-document pairs
            pairs = []
            for result in results:
                doc_text = result.get("metadata", {}).get("content_preview", "")
                if not doc_text:
                    doc_text = str(result.get("metadata", ""))
                pairs.append([query, doc_text])

            # Score with cross-encoder
            scores = self._model.predict(pairs)

            # Attach rerank scores
            for i, score in enumerate(scores):
                results[i]["rerank_score"] = float(score)

            # Sort by rerank score
            reranked = sorted(results, key=lambda x: x.get("rerank_score", 0), reverse=True)

            logger.info(f"Reranked {len(results)} results → top {top_k}")
            return reranked[:top_k]

        except Exception as e:
            logger.warning(f"Reranking failed: {e}. Returning original order.")
            return results[:top_k]
