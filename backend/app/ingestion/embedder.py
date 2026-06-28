"""
EKOS Document Embedder
Generates embeddings using Google Generative AI text-embedding-004 model.
"""

import time
from typing import Optional
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import get_settings
from app.utils.logger import logger
from app.utils.exceptions import IngestionError


class DocumentEmbedder:
    """Generate embeddings using Google Generative AI."""

    def __init__(self):
        self.settings = get_settings()
        genai.configure(api_key=self.settings.google_api_key)
        self.model_name = self.settings.embedding_model
        self.dimension = self.settings.embedding_dimension

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        reraise=True,
    )
    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: The text to embed

        Returns:
            List of floats (768-dimensional vector)
        """
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document",
            )
            return result["embedding"]
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise IngestionError(f"Failed to generate embedding: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        reraise=True,
    )
    def embed_query(self, query: str) -> list[float]:
        """
        Generate embedding for a search query.
        Uses 'retrieval_query' task type for better search performance.

        Args:
            query: The search query

        Returns:
            List of floats (768-dimensional vector)
        """
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=query,
                task_type="retrieval_query",
            )
            return result["embedding"]
        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            raise IngestionError(f"Failed to generate query embedding: {e}")

    def embed_batch(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.
        Handles rate limiting with batching and delays.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch

        Returns:
            List of embedding vectors
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            try:
                result = genai.embed_content(
                    model=self.model_name,
                    content=batch,
                    task_type="retrieval_document",
                )
                all_embeddings.extend(result["embedding"])
                logger.info(f"Embedded batch {i // batch_size + 1} ({len(batch)} texts)")
            except Exception as e:
                logger.warning(f"Batch embedding failed, falling back to individual: {e}")
                # Fallback to individual embedding
                for text in batch:
                    try:
                        emb = self.embed_text(text)
                        all_embeddings.append(emb)
                    except Exception as inner_e:
                        logger.error(f"Individual embedding failed: {inner_e}")
                        # Use zero vector as fallback
                        all_embeddings.append([0.0] * self.dimension)

            # Rate limit delay between batches
            if i + batch_size < len(texts):
                time.sleep(0.5)

        logger.info(f"Generated {len(all_embeddings)} embeddings total")
        return all_embeddings


# Singleton
_embedder: Optional[DocumentEmbedder] = None


def get_embedder() -> DocumentEmbedder:
    """Get or create the singleton embedder."""
    global _embedder
    if _embedder is None:
        _embedder = DocumentEmbedder()
    return _embedder
