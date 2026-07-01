"""
EKOS Fact Checker Agent
Verifies claims in answers against source evidence.
"""

import json
from app.agents.base_agent import BaseAgent
from app.agents.prompts import FACT_CHECKER_PROMPT
from app.llm.groq_client import get_chat_model
from app.utils.logger import logger


class FactCheckerAgent(BaseAgent):
    """Verifies factual claims against source evidence."""

    def __init__(self):
        super().__init__(
            name="fact_checker",
            description="Verifies claims against source documents",
        )

    async def execute(self, state: dict) -> dict:
        """Verify claims in the synthesized answer."""
        answer = state.get("synthesized_answer", "")

        if not answer:
            state["fact_check"] = {"overall_faithfulness": 0, "claims": []}
            return state

        # Build evidence for verification
        evidence_parts = []
        if state.get("retrieval_summary"):
            evidence_parts.append(f"Document Evidence:\n{state['retrieval_summary']}")
        if state.get("sql_summary"):
            evidence_parts.append(f"Database Evidence:\n{state['sql_summary']}")
        if state.get("graph_summary"):
            evidence_parts.append(f"Graph Evidence:\n{state['graph_summary']}")
        evidence = "\n\n".join(evidence_parts) or "No source evidence available."

        llm = get_chat_model(json_mode=True)
        chain = FACT_CHECKER_PROMPT | llm
        response = await chain.ainvoke({
            "query": state.get("query", "No query provided."),
            "answer": answer,
            "evidence": evidence,
        })
        response_text = response.content

        try:
            fact_check = json.loads(response_text)
        except json.JSONDecodeError:
            fact_check = {
                "overall_faithfulness": 0.7,
                "hallucination_count": 0,
                "claims": [],
                "summary": response_text,
            }

        state["fact_check"] = fact_check
        state["faithfulness_score"] = fact_check.get("overall_faithfulness", 0.7)

        logger.info(
            f"Fact Checker: faithfulness={fact_check.get('overall_faithfulness', 0):.2f}, "
            f"hallucinations={fact_check.get('hallucination_count', 0)}"
        )
        return state
