"""
EKOS Document Chunker
Splits parsed documents into smaller chunks for embedding and retrieval.
"""

import hashlib
import re
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
            content = self._normalize_text(page["content"])
            metadata = page.get("metadata", {})

            if not content.strip():
                continue

            if strategy == "sentence":
                texts = self._sentence_split(content)
            elif strategy == "fixed":
                texts = self._fixed_split(content)
            elif strategy == "markdown":
                texts = self._markdown_split(content)
            else:
                texts = self._recursive_split(content)

            for text in texts:
                cleaned = text.strip()
                if cleaned:
                    chunk = {
                        "content": cleaned,
                        "metadata": {
                            **metadata,
                            "chunk_index": chunk_index,
                            "chunk_size": len(cleaned),
                        },
                        "content_hash": self._hash_content(cleaned),
                        "token_count": self._estimate_tokens(cleaned),
                    }
                    all_chunks.append(chunk)
                    chunk_index += 1

        logger.info(f"Chunked {len(pages)} pages into {len(all_chunks)} chunks "
                     f"(strategy={strategy}, size={self.chunk_size}, overlap={self.chunk_overlap})")
        return all_chunks

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize whitespace in text before chunking.
        - Collapse 3+ newlines into double newlines (preserve paragraph breaks)
        - Replace tabs with single spaces
        - Collapse multiple spaces into one
        - Strip trailing whitespace per line
        """
        text = text.replace("\t", " ")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[^\S\n]+", " ", text)
        text = "\n".join(line.rstrip() for line in text.split("\n"))
        return text.strip()

    def _markdown_split(self, text: str) -> list[str]:
        """
        Split markdown text by headers, keeping sections together.
        Prepends the header context to each chunk to preserve meaning.
        """
        lines = text.split('\n')
        blocks = []
        current_context = []
        current_block_lines = []

        for line in lines:
            header_match = re.match(r'^(#+)\s+(.*)', line)
            if header_match:
                if current_block_lines:
                    content = "\n".join(current_block_lines).strip()
                    if content:
                        context_str = " > ".join(current_context)
                        blocks.append((context_str, content))
                    current_block_lines = []
                
                level = len(header_match.group(1))
                header_text = header_match.group(2).strip()
                
                if level <= len(current_context):
                    current_context = current_context[:level-1]
                current_context.append(header_text)
                current_block_lines.append(line)
            else:
                current_block_lines.append(line)
                
        if current_block_lines:
            content = "\n".join(current_block_lines).strip()
            if content:
                context_str = " > ".join(current_context)
                blocks.append((context_str, content))
                
        final_chunks = []
        for context_str, content in blocks:
            context_prefix = f"[Context: {context_str}]\n" if context_str else ""
            
            if len(context_prefix) + len(content) <= self.chunk_size:
                final_chunks.append(context_prefix + content)
            else:
                reduced_size = max(50, self.chunk_size - len(context_prefix))
                sub_chunks = self._recursive_split(content, max_size=reduced_size)
                for sc in sub_chunks:
                    final_chunks.append(context_prefix + sc)
                    
        return final_chunks

    def _recursive_split(self, text: str, max_size: Optional[int] = None) -> list[str]:
        """
        Recursively split text using hierarchical separators.
        Tries to keep semantically related text together.
        Overlap is applied ONLY here (top level), not inside the recursive calls.
        """
        target_size = max_size or self.chunk_size
        separators = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "]
        chunks = self._split_by_separators(text, separators, target_size)

        if self.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks)

        return chunks

    def _split_by_separators(self, text: str, separators: list[str], target_size: int) -> list[str]:
        """
        Split text using the first applicable separator.
        Preserves the separator at the end of the preceding segment
        so sentence-ending punctuation is not lost.
        """
        if len(text) <= target_size:
            return [text] if text.strip() else []

        separator = separators[0] if separators else " "
        remaining_separators = separators[1:] if len(separators) > 1 else separators

        # Split but keep the separator attached to the preceding part
        # e.g. splitting "Hello. World" on ". " gives ["Hello.", "World"]
        if separator.strip():
            # For punctuation-based separators like ". ", keep punct with left part
            parts = text.split(separator)
            # Re-attach separator to each part except the last
            rejoined_parts = []
            for idx, part in enumerate(parts):
                if idx < len(parts) - 1:
                    rejoined_parts.append(part + separator.rstrip())
                else:
                    rejoined_parts.append(part)
            parts = rejoined_parts
        else:
            # For whitespace separators ("\n\n", "\n", " "), simple split
            parts = text.split(separator)

        chunks = []
        current_chunk = ""

        for part in parts:
            if not part:
                continue

            if current_chunk:
                # Use a single space to join (separator is already attached)
                join_char = " " if separator.strip() else separator
                candidate = current_chunk + join_char + part
            else:
                candidate = part

            if len(candidate) <= target_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    if len(current_chunk) > target_size and remaining_separators:
                        sub_chunks = self._split_by_separators(
                            current_chunk, remaining_separators, target_size
                        )
                        chunks.extend(sub_chunks)
                    else:
                        chunks.append(current_chunk)

                current_chunk = part

        if current_chunk:
            if len(current_chunk) > target_size and remaining_separators:
                sub_chunks = self._split_by_separators(
                    current_chunk, remaining_separators, target_size
                )
                chunks.extend(sub_chunks)
            else:
                chunks.append(current_chunk)

        return chunks

    def _sentence_split(self, text: str) -> list[str]:
        """Split by sentences, grouping to fill chunk_size."""
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
        """
        Add overlap between consecutive chunks.
        Finds the nearest sentence boundary instead of cutting mid-word.
        """
        if not chunks:
            return chunks

        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]

            if len(prev_chunk) <= self.chunk_overlap:
                overlap_text = prev_chunk
            else:
                # Take roughly (chunk_overlap * 1.5) chars from the end to look for a sentence boundary
                search_size = int(self.chunk_overlap * 1.5)
                raw_overlap = prev_chunk[-search_size:] if search_size < len(prev_chunk) else prev_chunk
                
                # Try to find a sentence boundary
                import re
                match = re.search(r'([.!?]\s+|\n+)', raw_overlap)
                if match:
                    overlap_text = raw_overlap[match.end():].strip()
                    # If it's still way too long, fall back to word boundary near chunk_overlap
                    if len(overlap_text) > self.chunk_overlap * 1.2:
                        fallback = prev_chunk[-self.chunk_overlap:]
                        space_idx = fallback.find(" ")
                        overlap_text = fallback[space_idx + 1:] if space_idx != -1 else fallback
                else:
                    # Fallback to word boundary
                    fallback = prev_chunk[-self.chunk_overlap:]
                    space_idx = fallback.find(" ")
                    overlap_text = fallback[space_idx + 1:] if space_idx != -1 else fallback

            if overlap_text:
                overlapped.append(overlap_text + " " + chunks[i])
            else:
                overlapped.append(chunks[i])

        return overlapped

    @staticmethod
    def _hash_content(text: str) -> str:
        """Generate SHA-256 hash of content for deduplication."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation (4 chars per token)."""
        return len(text) // 4
