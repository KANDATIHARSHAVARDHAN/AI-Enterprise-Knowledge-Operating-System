"""
EKOS Hybrid Retriever
Combines dense (FAISS) and sparse (BM25) retrieval using Reciprocal Rank Fusion.
"""

from app.rag.dense_retriever import DenseRetriever
from app.rag.sparse_retriever import SparseRetriever
from app.config import get_settings
from app.utils.logger import logger


class HybridRetriever:
    """Combines dense and sparse retrieval with Reciprocal Rank Fusion."""

    def __init__(self, sparse_retriever: SparseRetriever = None):
        self.settings = get_settings()
        self.dense_retriever = DenseRetriever()
        self.sparse_retriever = sparse_retriever or SparseRetriever()
        self.dense_weight = self.settings.dense_weight
        self.sparse_weight = self.settings.sparse_weight

    def retrieve(self, query: str, top_k: int = None) -> list[dict]:
        """
        Perform hybrid retrieval combining dense and sparse results.

        Uses Reciprocal Rank Fusion (RRF) to merge ranked lists.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            Fused list of results sorted by RRF score
        """
        top_k = top_k or self.settings.top_k_retrieval

        # Get results from both retrievers
        dense_results = self.dense_retriever.retrieve(query, top_k=top_k * 2)
        sparse_results = self.sparse_retriever.retrieve(query, top_k=top_k * 2)

        # Apply Reciprocal Rank Fusion
        fused = self._reciprocal_rank_fusion(
            dense_results, sparse_results, k=60
        )

        # Sort by fused score and take top_k
        fused.sort(key=lambda x: x["rrf_score"], reverse=True)
        results = fused[:top_k]

        logger.info(
            f"Hybrid retrieval: {len(dense_results)} dense + {len(sparse_results)} sparse "
            f"→ {len(results)} fused results"
        )

        return results

    def _reciprocal_rank_fusion(
        self,
        dense_results: list[dict],
        sparse_results: list[dict],
        k: int = 60,
    ) -> list[dict]:
        """
        Merge results using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank)) for each ranking list

        Args:
            dense_results: Results from dense retrieval
            sparse_results: Results from sparse retrieval
            k: RRF constant (default 60)

        Returns:
            Merged list with rrf_score
        """
        rrf_scores = {}
        result_data = {}

        # Score dense results
        for rank, result in enumerate(dense_results, 1):
            key = self._result_key(result)
            rrf_scores[key] = rrf_scores.get(key, 0) + self.dense_weight * (1 / (k + rank))
            result_data[key] = result

        # Score sparse results
        for rank, result in enumerate(sparse_results, 1):
            key = self._result_key(result)
            rrf_scores[key] = rrf_scores.get(key, 0) + self.sparse_weight * (1 / (k + rank))
            if key not in result_data:
                result_data[key] = result

        # Combine
        fused = []
        for key, score in rrf_scores.items():
            result = result_data[key].copy()
            result["rrf_score"] = score
            result["original_score"] = result.get("score", 0)
            fused.append(result)

        return fused

    @staticmethod
    def _result_key(result: dict) -> str:
        """Generate a unique key for a result based on its metadata."""
        metadata = result.get("metadata", {})
        return metadata.get("embedding_id", metadata.get("content_preview", "")[:100])
