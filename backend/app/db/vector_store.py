"""
EKOS FAISS Vector Store
Manages FAISS index for dense vector retrieval with metadata mapping.
"""

import json
import numpy as np
from pathlib import Path
from typing import Optional
import faiss
from app.config import get_settings
from app.utils.logger import logger


class VectorStore:
    """FAISS-based vector store with metadata mapping."""

    def __init__(self):
        self.settings = get_settings()
        self.dimension = self.settings.embedding_dimension
        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata: list[dict] = []
        self.id_map: dict[str, int] = {}  # embedding_id → position in index

        self._index_path = Path(self.settings.faiss_index_path)
        self._metadata_path = Path(self.settings.faiss_metadata_path)

        self._initialize()

    def _initialize(self):
        """Load existing index or create new one."""
        if self._index_path.exists() and self._metadata_path.exists():
            self._load()
        else:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []
            self.id_map = {}
            logger.info(f"Created new FAISS index (dim={self.dimension})")

    def add_embeddings(
        self,
        embeddings: list[list[float]],
        metadata_list: list[dict],
        embedding_ids: list[str],
    ):
        """
        Add embeddings to the FAISS index.

        Args:
            embeddings: List of embedding vectors
            metadata_list: List of metadata dicts for each vector
            embedding_ids: Unique identifiers for each embedding
        """
        if not embeddings:
            return

        # Normalize embeddings for cosine similarity (IndexFlatIP)
        vectors = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(vectors)

        start_pos = self.index.ntotal

        self.index.add(vectors)

        for i, (meta, emb_id) in enumerate(zip(metadata_list, embedding_ids)):
            position = start_pos + i
            self.metadata.append(meta)
            self.id_map[emb_id] = position

        logger.info(f"Added {len(embeddings)} vectors to FAISS (total: {self.index.ntotal})")

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
    ) -> list[dict]:
        """
        Search for similar vectors in the index.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return

        Returns:
            List of dicts with 'score', 'metadata' for each match
        """
        if self.index.ntotal == 0:
            return []

        # Normalize query vector
        query = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query)

        # Search
        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.metadata):
                results.append({
                    "score": float(score),
                    "metadata": self.metadata[idx],
                })

        return results

    def delete_by_document(self, document_id: int):
        """
        Remove all vectors for a specific document.
        Note: FAISS doesn't support individual deletion efficiently,
        so we rebuild the index without the deleted vectors.
        """
        indices_to_keep = []
        new_metadata = []
        new_id_map = {}

        for i, meta in enumerate(self.metadata):
            if meta.get("document_id") != document_id:
                indices_to_keep.append(i)

        if len(indices_to_keep) == len(self.metadata):
            return  # Nothing to delete

        if not indices_to_keep:
            # Delete everything
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []
            self.id_map = {}
            self.save()
            return

        # Reconstruct vectors for kept indices
        vectors = np.zeros((len(indices_to_keep), self.dimension), dtype=np.float32)
        for new_idx, old_idx in enumerate(indices_to_keep):
            vectors[new_idx] = self.index.reconstruct(old_idx)
            meta = self.metadata[old_idx]
            new_metadata.append(meta)
            emb_id = meta.get("embedding_id", f"vec_{new_idx}")
            new_id_map[emb_id] = new_idx

        # Rebuild index
        new_index = faiss.IndexFlatIP(self.dimension)
        new_index.add(vectors)

        self.index = new_index
        self.metadata = new_metadata
        self.id_map = new_id_map
        self.save()

        logger.info(f"Deleted vectors for document {document_id}. "
                     f"Remaining: {self.index.ntotal}")

    def save(self):
        """Save the FAISS index and metadata to disk."""
        self._index_path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, str(self._index_path))

        with open(self._metadata_path, "w") as f:
            json.dump({
                "metadata": self.metadata,
                "id_map": self.id_map,
            }, f)

        logger.info(f"Saved FAISS index ({self.index.ntotal} vectors)")

    def _load(self):
        """Load FAISS index and metadata from disk."""
        try:
            self.index = faiss.read_index(str(self._index_path))

            with open(self._metadata_path, "r") as f:
                data = json.load(f)

            self.metadata = data.get("metadata", [])
            self.id_map = data.get("id_map", {})

            logger.info(f"Loaded FAISS index ({self.index.ntotal} vectors)")
        except Exception as e:
            logger.warning(f"Failed to load FAISS index, creating new: {e}")
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []
            self.id_map = {}

    @property
    def total_vectors(self) -> int:
        """Get total number of vectors in the index."""
        return self.index.ntotal if self.index else 0

    def get_stats(self) -> dict:
        """Get vector store statistics."""
        return {
            "total_vectors": self.total_vectors,
            "dimension": self.dimension,
            "index_path": str(self._index_path),
            "index_exists": self._index_path.exists(),
        }


# Singleton
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create the singleton vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
