"""
EKOS Sparse Retriever
BM25-based sparse retrieval for keyword matching.
"""

import re
from typing import Optional
from rank_bm25 import BM25Okapi
from app.utils.logger import logger


class SparseRetriever:
    """BM25-based sparse retrieval for keyword-focused search."""

    def __init__(self):
        self.bm25: Optional[BM25Okapi] = None
        self.documents: list[dict] = []
        self.tokenized_corpus: list[list[str]] = []
        self._is_manually_indexed = False

    def build_index(self, documents: list[dict], is_manual: bool = True):
        """
        Build BM25 index from a list of document chunks.

        Args:
            documents: List of dicts with 'content' and 'metadata'
            is_manual: Whether this index is built manually (disables auto-sync)
        """
        self.documents = documents
        self.tokenized_corpus = [
            self._tokenize(doc.get("content", "")) for doc in documents
        ]
        self._is_manually_indexed = is_manual

        if self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)
            logger.info(f"Built BM25 index with {len(documents)} documents")

    def _sync_from_vector_store(self):
        """Sync documents and build BM25 index from FAISS vector store metadata."""
        if self._is_manually_indexed:
            return

        try:
            from app.db.vector_store import get_vector_store
            vs = get_vector_store()
            if vs.metadata and (not self.documents or len(self.documents) != len(vs.metadata)):
                docs = []
                for meta in vs.metadata:
                    content = meta.get("content", meta.get("content_preview", ""))
                    docs.append({
                        "content": content,
                        "metadata": meta,
                    })
                self.build_index(docs, is_manual=False)
        except Exception as e:
            logger.warning(f"Failed to auto-sync sparse retriever from vector store: {e}")

    def retrieve(self, query: str, top_k: int = 10) -> list[dict]:
        """
        Retrieve documents using BM25 scoring.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of results with score and metadata
        """
        self._sync_from_vector_store()

        if not self.bm25 or not self.documents:
            return []

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                doc = self.documents[idx]
                results.append({
                    "score": float(scores[idx]),
                    "metadata": doc.get("metadata", {}),
                    "content": doc.get("content", ""),
                    "content_preview": doc.get("content", "")[:200],
                })

        logger.info(f"Sparse retrieval: {len(results)} results for '{query[:50]}...'")
        return results

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple tokenization: lowercase, split, remove punctuation."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        tokens = text.split()
        # Remove very short tokens
        return [t for t in tokens if len(t) > 1]
