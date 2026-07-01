"""
EKOS Retriever Agent
Performs hybrid RAG retrieval with reranking.
"""

import json
from app.agents.base_agent import BaseAgent
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import Reranker
from app.rag.query_rewriter import QueryRewriter
from app.agents.prompts import RETRIEVER_PROMPT
from app.llm.groq_client import get_chat_model
from app.config import get_settings
from app.utils.logger import logger


class RetrieverAgent(BaseAgent):
    """Performs document retrieval using hybrid RAG pipeline."""

    def __init__(self, hybrid_retriever: HybridRetriever = None):
        super().__init__(
            name="retriever",
            description="Searches documents using hybrid dense+sparse retrieval",
        )
        self.retriever = hybrid_retriever or HybridRetriever()
        self.reranker = Reranker()
        self.query_rewriter = QueryRewriter()
        self.settings = get_settings()

    async def execute(self, state: dict) -> dict:
        """Execute retrieval for the current query or sub-tasks."""
        query = state.get("query", "")
        sub_tasks = state.get("sub_tasks", [])

        # Get retriever-specific sub-tasks
        retriever_tasks = [
            t for t in sub_tasks if t.get("agent") == "RETRIEVER"
        ]

        search_queries = []
        if retriever_tasks:
            for task in retriever_tasks:
                search_queries.append(task.get("search_query", query))
        else:
            search_queries = [query]

        # Optionally rewrite queries for better recall
        expanded_queries = []
        for sq in search_queries:
            rewritten = await self.query_rewriter.rewrite(sq)
            expanded_queries.extend(rewritten)

        # Deduplicate
        expanded_queries = list(dict.fromkeys(expanded_queries))

        # Retrieve documents for all queries
        all_results = []
        seen_keys = set()

        for search_query in expanded_queries[:5]:  # Limit to 5 queries
            results = self.retriever.retrieve(search_query, top_k=self.settings.top_k_retrieval)
            for r in results:
                key = r.get("metadata", {}).get("embedding_id", str(r.get("metadata", "")))
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_results.append(r)

        # Rerank combined results
        reranked = self.reranker.rerank(query, all_results, top_k=self.settings.top_k_rerank)

        # Analyze results with LLM
        chunks_text = "\n\n---\n\n".join([
            f"[Source: {r.get('metadata', {}).get('source', 'Unknown')}]\n"
            f"{r.get('content') or r.get('metadata', {}).get('content') or r.get('metadata', {}).get('content_preview', '')}"
            for r in reranked
        ])

        llm = get_chat_model(json_mode=True)
        chain = RETRIEVER_PROMPT | llm
        response_text = ""
        
        try:
            response = await chain.ainvoke({
                "task": "Document retrieval and analysis",
                "query": query,
                "retrieved_chunks": chunks_text or "No documents found.",
            })
            response_text = response.content
        except Exception as e:
            logger.warning(
                f"Retriever LLM json_mode=True failed: {e}. Retrying without JSON mode constraint...",
                extra={"agent_name": self.name}
            )
            try:
                fallback_llm = get_chat_model(json_mode=False)
                fallback_chain = RETRIEVER_PROMPT | fallback_llm
                response = await fallback_chain.ainvoke({
                    "task": "Document retrieval and analysis",
                    "query": query,
                    "retrieved_chunks": chunks_text or "No documents found.",
                })
                response_text = response.content
            except Exception as fe:
                logger.error(
                    f"Retriever fallback LLM invocation failed: {fe}",
                    extra={"agent_name": self.name}
                )

        retrieval_result = None
        if response_text:
            cleaned_text = response_text.strip()
            # If wrapped in markdown code fence, extract the content inside
            if cleaned_text.startswith("```"):
                lines = cleaned_text.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned_text = "\n".join(lines).strip()
            
            try:
                retrieval_result = json.loads(cleaned_text)
            except json.JSONDecodeError as jde:
                logger.warning(
                    f"Failed to parse retriever LLM response as JSON: {jde}. Raw response: {response_text[:200]}...",
                    extra={"agent_name": self.name}
                )

        if not retrieval_result:
            summary_text = response_text if response_text else "No response generated by retriever."
            retrieval_result = {
                "relevant_findings": [
                    {
                        "content": r.get('content') or r.get('metadata', {}).get('content') or r.get('metadata', {}).get('content_preview', ''),
                        "source": r.get('metadata', {}).get('source', 'Unknown'),
                        "relevance_score": 0.5,
                        "citation": f"[Source: {r.get('metadata', {}).get('source', 'Unknown')}]"
                    }
                    for r in reranked[:3]
                ],
                "summary": summary_text,
                "confidence": 0.5 if response_text else 0.0,
            }

        # Store results in state
        state["retrieved_chunks"] = reranked
        state["retrieval_analysis"] = retrieval_result
        state["retrieval_summary"] = retrieval_result.get("summary", "")

        logger.info(f"Retrieval complete: {len(reranked)} reranked results")
        return state
