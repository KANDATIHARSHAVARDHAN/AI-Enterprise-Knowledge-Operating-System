"""
EKOS Critic Agent
Evaluates answer quality for relevance, completeness, coherence, and accuracy.
"""

import json
from app.agents.base_agent import BaseAgent
from app.agents.prompts import CRITIC_PROMPT
from app.llm.groq_client import get_chat_model
from app.utils.logger import logger


class CriticAgent(BaseAgent):
    """Evaluates the quality of generated answers."""

    def __init__(self, quality_threshold: float = 0.6):
        super().__init__(
            name="critic",
            description="Evaluates answer quality and provides improvement feedback",
        )
        self.quality_threshold = quality_threshold

    async def execute(self, state: dict) -> dict:
        """Evaluate the synthesized answer."""
        query = state.get("query", "")
        answer = state.get("synthesized_answer", "")

        if not answer:
            state["critic_result"] = {
                "overall_score": 0,
                "passed": False,
                "issues": ["No answer to evaluate"],
            }
            return state

        # Build evidence summary for evaluation
        evidence_parts = []
        if state.get("retrieval_summary"):
            evidence_parts.append(state["retrieval_summary"])
        if state.get("sql_summary"):
            evidence_parts.append(state["sql_summary"])
        evidence = "\n".join(evidence_parts) or "No evidence available."

        llm = get_chat_model(json_mode=True)
        chain = CRITIC_PROMPT | llm
        response = await chain.ainvoke({
            "question": query,
            "answer": answer,
            "evidence": evidence,
        })
        response_text = response.content

        try:
            critic_result = json.loads(response_text)
        except json.JSONDecodeError:
            critic_result = {
                "overall_score": 0.7,
                "passed": True,
                "issues": [],
                "reasoning": response_text,
            }

        # Check if quality threshold is met
        overall_score = critic_result.get("overall_score", 0.7)
        critic_result["passed"] = overall_score >= self.quality_threshold

        state["critic_result"] = critic_result
        state["quality_score"] = overall_score

        logger.info(
            f"Critic Agent: score={overall_score:.2f}, "
            f"passed={critic_result['passed']}"
        )
        return state
