"""
EKOS Planner Agent
Decomposes complex queries into ordered sub-tasks with agent assignments.
"""

import json
from app.agents.base_agent import BaseAgent
from app.agents.prompts import PLANNER_PROMPT
from app.llm.groq_client import get_chat_model
from app.utils.logger import logger


class PlannerAgent(BaseAgent):
    """Decomposes complex user queries into structured execution plans."""

    def __init__(self):
        super().__init__(
            name="planner",
            description="Decomposes queries into sub-tasks for specialist agents",
        )

    async def execute(self, state: dict) -> dict:
        """Create an execution plan for the given query."""
        query = state.get("query", "")
        context = state.get("conversation_context", "No previous context")

        llm = get_chat_model(json_mode=True)
        chain = PLANNER_PROMPT | llm
        response = await chain.ainvoke({"query": query, "context": context})
        response_text = response.content

        try:
            plan = json.loads(response_text)
        except json.JSONDecodeError:
            plan = {
                "query_understanding": query,
                "complexity": "simple",
                "sub_tasks": [
                    {
                        "id": 1,
                        "agent": "RETRIEVER",
                        "task": f"Search for information about: {query}",
                        "search_query": query,
                        "depends_on": [],
                        "priority": "high",
                    }
                ],
                "reasoning": "Fallback to simple retrieval plan",
            }

        state["plan"] = plan
        state["sub_tasks"] = plan.get("sub_tasks", [])
        state["complexity"] = plan.get("complexity", "simple")

        logger.info(
            f"Plan created: {len(state['sub_tasks'])} sub-tasks, "
            f"complexity={state['complexity']}"
        )

        return state
