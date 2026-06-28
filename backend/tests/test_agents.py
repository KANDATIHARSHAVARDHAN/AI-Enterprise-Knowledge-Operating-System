"""
EKOS Agent Unit Tests
Tests the planner agent and orchestrator behavior using mocks.
"""

import pytest
from app.agents.planner_agent import PlannerAgent
from app.agents.orchestrator import AgentOrchestrator


@pytest.mark.asyncio
async def test_planner_agent(mock_groq, mock_embedder):
    """Test that the planner correctly decomposes a query."""
    # Set mock response for planner
    mock_groq.chat.return_value = """
    {
      "query_understanding": "Why did Machine X fail?",
      "complexity": "simple",
      "sub_tasks": [
        {
          "id": 1,
          "agent": "SQL_AGENT",
          "task": "Query machine events",
          "search_query": "Machine X failures",
          "depends_on": [],
          "priority": "high"
        }
      ],
      "reasoning": "Simple SQL query needed"
    }
    """

    planner = PlannerAgent()
    state = {"query": "Why did Machine X fail?", "conversation_context": "No context"}
    updated_state = await planner.execute(state)

    assert updated_state["complexity"] == "simple"
    assert len(updated_state["sub_tasks"]) == 1
    assert updated_state["sub_tasks"][0]["agent"] == "SQL_AGENT"


@pytest.mark.asyncio
async def test_orchestrator_routing():
    """Test routing logic of the orchestrator."""
    orchestrator = AgentOrchestrator()

    # Route after planning with only retrieval
    state_retriever = {
        "sub_tasks": [{"agent": "RETRIEVER", "task": "search"}]
    }
    route = orchestrator._route_after_planning(state_retriever)
    assert route == "retriever"

    # Route after planning with only SQL
    state_sql = {
        "sub_tasks": [{"agent": "SQL_AGENT", "task": "query"}]
    }
    route = orchestrator._route_after_planning(state_sql)
    assert route == "sql_agent"

    # Route after planning with both
    state_both = {
        "sub_tasks": [
            {"agent": "RETRIEVER", "task": "search"},
            {"agent": "SQL_AGENT", "task": "query"}
        ]
    }
    route = orchestrator._route_after_planning(state_both)
    assert route == "both"
