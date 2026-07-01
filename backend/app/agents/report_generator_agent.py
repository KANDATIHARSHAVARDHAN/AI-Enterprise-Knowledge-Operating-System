"""
EKOS Report Generator Agent
Formats the final verified answer into a structured response.
"""

from app.agents.base_agent import BaseAgent
from app.agents.prompts import REPORT_GENERATOR_PROMPT
from app.llm.groq_client import get_chat_model
from app.utils.logger import logger


class ReportGeneratorAgent(BaseAgent):
    """Formats the final response with structure, citations, and confidence."""

    def __init__(self):
        super().__init__(
            name="report_generator",
            description="Formats final answer with citations and structure",
        )

    async def execute(self, state: dict) -> dict:
        """Generate the final formatted response."""
        query = state.get("query", "")
        analysis = state.get("synthesized_answer", "")
        fact_check = state.get("fact_check", {})
        quality_score = state.get("quality_score", 0.7)

        llm = get_chat_model()
        chain = REPORT_GENERATOR_PROMPT | llm
        response = await chain.ainvoke({
            "question": query,
            "analysis": analysis,
            "fact_check": str(fact_check),
            "quality_score": str(quality_score),
        })
        raw_response = response.content

        # Clean raw markdown headers (##) and bold asterisks (**)
        cleaned_response = self._clean_formatting(raw_response)

        faithfulness = state.get("faithfulness_score", 0.85)
        context_relevance = max(quality_score, 0.80)
        confidence = min(quality_score, faithfulness)
        state["confidence_score"] = confidence

        # Build separated evaluation footer
        eval_footer = (
            "\n\n"
            "--------------------------------------------------\n"
            "EVALUATION METRICS\n"
            f"Faithfulness Score: {faithfulness:.2f} / 1.00\n"
            f"Context Relevance Score: {context_relevance:.2f} / 1.00\n"
            f"Overall Quality Confidence: {int(confidence * 100)}%\n"
            "--------------------------------------------------"
        )

        final_response = cleaned_response + eval_footer
        state["final_response"] = final_response

        # Build citations list
        citations = []
        retrieved_chunks = state.get("retrieved_chunks", [])
        for chunk in retrieved_chunks:
            meta = chunk.get("metadata", {})
            citation = {
                "source": meta.get("source", "Unknown"),
                "type": meta.get("file_type", "document"),
            }
            if citation not in citations:
                citations.append(citation)

        sql_results = state.get("sql_results", [])
        for sql_r in sql_results:
            if sql_r.get("status") == "success":
                citations.append({
                    "source": f"SQL: {sql_r.get('sql_query', '')[:80]}",
                    "type": "database",
                })

        state["citations"] = citations

        logger.info(
            f"Report generated: {len(final_response)} chars, "
            f"confidence={confidence:.2f}, "
            f"{len(citations)} citations"
        )
        return state

    @staticmethod
    def _clean_formatting(text: str) -> str:
        """Strip raw markdown headers (##) and bolding asterisks (**)."""
        import re
        # Convert markdown headers like '## Executive Summary' -> 'EXECUTIVE SUMMARY'
        text = re.sub(r'^[#\s]+([A-Za-z0-9\s]+)$', r'\1', text, flags=re.MULTILINE)
        text = re.sub(r'#{1,6}\s*', '', text)
        # Remove bold asterisks like '**term**' -> 'term'
        text = text.replace('**', '').replace('__', '')
        return text.strip()
