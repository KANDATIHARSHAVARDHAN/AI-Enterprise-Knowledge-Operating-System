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
        final_response = response.content

        state["final_response"] = final_response
        state["confidence_score"] = min(
            quality_score,
            state.get("faithfulness_score", 0.7),
        )

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
            f"confidence={state['confidence_score']:.2f}, "
            f"{len(citations)} citations"
        )
        return state
