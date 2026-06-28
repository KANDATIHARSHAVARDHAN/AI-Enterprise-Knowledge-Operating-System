"""
EKOS Dense Retriever
FAISS-based dense retrieval using Google Generative AI embeddings.
"""

from app.db.vector_store import get_vector_store
from app.ingestion.embedder import get_embedder
from app.utils.logger import logger


class DenseRetriever:
    """Dense retrieval using FAISS vector similarity search."""

    def __init__(self):
        self.vector_store = get_vector_store()
        self.embedder = get_embedder()

    def retrieve(self, query: str, top_k: int = 10) -> list[dict]:
        """
        Retrieve documents using dense vector search.

        Args:
            query: Search query string
            top_k: Number of results to return

        Returns:
            List of results with score, metadata, and content_preview
        """
        # Generate query embedding
        query_embedding = self.embedder.embed_query(query)

        # Search FAISS
        results = self.vector_store.search(query_embedding, top_k=top_k)

        logger.info(f"Dense retrieval: {len(results)} results for '{query[:50]}...'")
        return results
