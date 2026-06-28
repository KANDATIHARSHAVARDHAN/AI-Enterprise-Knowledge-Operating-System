"""
EKOS Query Rewriter
Uses LLM to expand and reformulate queries for better retrieval.
"""

import json
from app.llm.groq_client import get_groq_client
from app.utils.logger import logger


class QueryRewriter:
    """LLM-based query expansion and reformulation."""

    async def rewrite(self, query: str, context: str = "") -> list[str]:
        """
        Generate multiple search queries from a single user query.

        Args:
            query: Original user query
            context: Optional conversation context

        Returns:
            List of expanded search queries (including original)
        """
        client = get_groq_client()

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a search query optimizer. Given a user question, generate 3 diverse "
                    "search queries that would help find relevant information. Include:\n"
                    "1. A more specific version of the query\n"
                    "2. A broader version using different terminology\n"
                    "3. A query focusing on a different aspect\n"
                    "Return a JSON array of strings."
                ),
            },
            {
                "role": "user",
                "content": f"User question: {query}\nContext: {context}\n\nGenerate 3 search queries as a JSON array.",
            },
        ]

        try:
            response = await client.chat_with_fast_model(
                messages=messages,
                json_mode=True,
                max_tokens=500,
            )

            queries = json.loads(response)
            if isinstance(queries, dict):
                queries = queries.get("queries", [query])
            if isinstance(queries, list):
                # Always include original query
                result = [query] + [q for q in queries if q != query]
                logger.info(f"Rewrote query into {len(result)} variants")
                return result[:4]  # Max 4 queries

        except Exception as e:
            logger.warning(f"Query rewriting failed: {e}")

        return [query]  # Fallback to original query


class ContextCompressor:
    """LLM-based context compression to reduce noise in retrieved chunks."""

    async def compress(self, query: str, chunks: list[str]) -> list[str]:
        """
        Compress retrieved chunks by removing irrelevant parts.

        Args:
            query: The user's original query
            chunks: List of retrieved text chunks

        Returns:
            List of compressed chunks (relevant parts only)
        """
        if not chunks:
            return []

        client = get_groq_client()
        compressed = []

        for chunk in chunks:
            if len(chunk) < 100:
                compressed.append(chunk)
                continue

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Extract only the sentences from the following text that are relevant "
                        "to answering the user's question. Remove irrelevant information. "
                        "If nothing is relevant, respond with 'NOT_RELEVANT'."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {query}\n\nText:\n{chunk}",
                },
            ]

            try:
                response = await client.chat_with_fast_model(
                    messages=messages,
                    max_tokens=500,
                )
                if response.strip() != "NOT_RELEVANT":
                    compressed.append(response.strip())
            except Exception:
                compressed.append(chunk)  # Keep original on error

        logger.info(f"Compressed {len(chunks)} chunks → {len(compressed)} relevant chunks")
        return compressed
