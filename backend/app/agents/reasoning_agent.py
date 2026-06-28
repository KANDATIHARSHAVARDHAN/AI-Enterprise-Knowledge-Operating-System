"""
EKOS Reasoning Agent
Synthesizes evidence from multiple sources into coherent analysis.
"""

import json
from app.agents.base_agent import BaseAgent
from app.agents.prompts import REASONING_PROMPT
from app.llm.groq_client import get_chat_model
from app.utils.logger import logger


class ReasoningAgent(BaseAgent):
    """Synthesizes evidence from all agents into a coherent analysis."""

    def __init__(self):
        super().__init__(
            name="reasoning",
            description="Synthesizes multi-source evidence into coherent analysis",
        )

    async def execute(self, state: dict) -> dict:
        """Synthesize all gathered evidence."""
        query = state.get("query", "")

        # Gather all evidence from previous agents
        evidence_parts = []

        # Retrieval results
        retrieval = state.get("retrieval_summary", "")
        if retrieval:
            evidence_parts.append(f"## Document Retrieval Results\n{retrieval}")

        # SQL results
        sql_summary = state.get("sql_summary", "")
        if sql_summary:
            evidence_parts.append(f"## Database Query Results\n{sql_summary}")

        # Graph results
        graph_summary = state.get("graph_summary", "")
        if graph_summary:
            evidence_parts.append(f"## Knowledge Graph Relationships\n{graph_summary}")

        # Vision results
        vision_results = state.get("vision_results", {})
        if isinstance(vision_results, list) and vision_results:
            vision_text = "\n".join([
                f"Image: {v.get('source', 'unknown')} - {v.get('analysis', v.get('visual_description', ''))}"
                for v in vision_results
            ])
            evidence_parts.append(f"## Image Analysis\n{vision_text}")

        # Memory context
        memory = state.get("memory_context", "")
        if memory:
            evidence_parts.append(f"## Conversation Memory\n{memory}")

        evidence = "\n\n".join(evidence_parts) if evidence_parts else "No evidence gathered."

        # Use LLM to synthesize
        llm = get_chat_model(json_mode=True)
        chain = REASONING_PROMPT | llm
        response = await chain.ainvoke({
            "query": query,
            "evidence": evidence,
        })
        response_text = response.content

        try:
            analysis = json.loads(response_text)
        except json.JSONDecodeError:
            analysis = {
                "analysis": response_text,
                "key_findings": [],
                "patterns_identified": [],
                "root_causes": [],
                "recommendations": [],
            }

        state["reasoning_analysis"] = analysis
        state["synthesized_answer"] = analysis.get("analysis", response_text)

        logger.info(f"Reasoning Agent synthesized {len(evidence_parts)} evidence sources")
        return state
