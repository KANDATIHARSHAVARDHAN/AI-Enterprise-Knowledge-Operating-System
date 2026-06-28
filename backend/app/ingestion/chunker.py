"""
EKOS Document Chunker
Splits parsed documents into smaller chunks for embedding and retrieval.
"""

import hashlib
from typing import Optional
from app.config import get_settings
from app.utils.logger import logger


class DocumentChunker:
    """Split documents into chunks with configurable strategies."""

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ):
        settings = get_settings()
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    def chunk_documents(
        self,
        pages: list[dict],
        strategy: str = "recursive",
    ) -> list[dict]:
        """
        Chunk parsed documents into smaller pieces.

        Args:
            pages: List of parsed page dicts from parsers
            strategy: Chunking strategy - 'recursive', 'sentence', or 'fixed'

        Returns:
            List of chunk dicts with content, metadata, and content_hash
        """
        all_chunks = []
        chunk_index = 0

        for page in pages:
            content = page["content"]
            metadata = page.get("metadata", {})

            if strategy == "sentence":
                texts = self._sentence_split(content)
            elif strategy == "fixed":
                texts = self._fixed_split(content)
            else:
                texts = self._recursive_split(content)

            for text in texts:
                if text.strip():
                    chunk = {
                        "content": text.strip(),
                        "metadata": {
                            **metadata,
                            "chunk_index": chunk_index,
                            "chunk_size": len(text),
                        },
                        "content_hash": self._hash_content(text),
                        "token_count": self._estimate_tokens(text),
                    }
                    all_chunks.append(chunk)
                    chunk_index += 1

        logger.info(f"Chunked {len(pages)} pages into {len(all_chunks)} chunks "
                     f"(strategy={strategy}, size={self.chunk_size}, overlap={self.chunk_overlap})")
        return all_chunks

    def _recursive_split(self, text: str) -> list[str]:
        """
        Recursively split text using hierarchical separators.
        Tries to keep semantically related text together.
        """
        separators = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "]
        return self._split_by_separators(text, separators)

    def _split_by_separators(self, text: str, separators: list[str]) -> list[str]:
        """Split text using the first applicable separator."""
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        separator = separators[0] if separators else " "
        remaining_separators = separators[1:] if len(separators) > 1 else separators

        parts = text.split(separator)
        chunks = []
        current_chunk = ""

        for part in parts:
            candidate = current_chunk + separator + part if current_chunk else part

            if len(candidate) <= self.chunk_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    if len(current_chunk) > self.chunk_size and remaining_separators:
                        # Recursively split with finer separator
                        sub_chunks = self._split_by_separators(
                            current_chunk, remaining_separators
                        )
                        chunks.extend(sub_chunks)
                    else:
                        chunks.append(current_chunk)

                current_chunk = part

        if current_chunk:
            if len(current_chunk) > self.chunk_size and remaining_separators:
                sub_chunks = self._split_by_separators(
                    current_chunk, remaining_separators
                )
                chunks.extend(sub_chunks)
            else:
                chunks.append(current_chunk)

        # Apply overlap
        if self.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks)

        return chunks

    def _sentence_split(self, text: str) -> list[str]:
        """Split by sentences, grouping to fill chunk_size."""
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            candidate = current_chunk + " " + sentence if current_chunk else sentence
            if len(candidate) <= self.chunk_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        if self.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks)

        return chunks

    def _fixed_split(self, text: str) -> list[str]:
        """Simple fixed-size character splitting."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - self.chunk_overlap if self.chunk_overlap > 0 else end
        return chunks

    def _apply_overlap(self, chunks: list[str]) -> list[str]:
        """Add overlap between consecutive chunks."""
        if not chunks:
            return chunks

        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            overlap_text = prev_chunk[-self.chunk_overlap:] if len(prev_chunk) > self.chunk_overlap else prev_chunk
            overlapped.append(overlap_text + " " + chunks[i])

        return overlapped

    @staticmethod
    def _hash_content(text: str) -> str:
        """Generate SHA-256 hash of content for deduplication."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation (4 chars per token)."""
        return len(text) // 4
