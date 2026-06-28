"""
EKOS Multi-Agent Orchestrator
Uses LangGraph to orchestrate the multi-agent workflow with conditional routing.
"""

import time
from typing import TypedDict
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.planner_agent import PlannerAgent
from app.agents.retriever_agent import RetrieverAgent
from app.agents.sql_agent import SQLAgent
from app.agents.vision_agent import VisionAgent
from app.agents.graph_agent import GraphAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.reasoning_agent import ReasoningAgent
from app.agents.critic_agent import CriticAgent
from app.agents.fact_checker_agent import FactCheckerAgent
from app.agents.report_generator_agent import ReportGeneratorAgent
from app.utils.logger import logger


class AgentState(TypedDict, total=False):
    """State shared across all agents in the workflow."""
    # Input
    query: str
    user_id: int
    conversation_id: int
    image_paths: list

    # Planning
    plan: dict
    sub_tasks: list
    complexity: str
    conversation_context: str

    # Agent results
    retrieved_chunks: list
    retrieval_analysis: dict
    retrieval_summary: str
    sql_results: list
    sql_summary: str
    vision_results: dict
    graph_results: dict
    graph_summary: str
    memory_context: str
    memory_data: dict

    # Synthesis
    reasoning_analysis: dict
    synthesized_answer: str

    # Verification
    critic_result: dict
    quality_score: float
    fact_check: dict
    faithfulness_score: float

    # Output
    final_response: str
    confidence_score: float
    citations: list
    agent_trace: list

    # Control
    retry_count: int
    error: str


class AgentOrchestrator:
    """LangGraph-based multi-agent orchestrator."""

    def __init__(self, db_session: AsyncSession = None):
        self.db_session = db_session

        # Initialize agents
        self.planner = PlannerAgent()
        self.retriever = RetrieverAgent()
        self.sql_agent = SQLAgent(db_session=db_session)
        self.vision_agent = VisionAgent()
        self.graph_agent = GraphAgent()
        self.memory_agent = MemoryAgent(db_session=db_session)
        self.reasoning_agent = ReasoningAgent()
        self.critic_agent = CriticAgent()
        self.fact_checker = FactCheckerAgent()
        self.report_generator = ReportGeneratorAgent()

        # Build the workflow graph
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph state graph for agent orchestration."""
        workflow = StateGraph(AgentState)

        # Add nodes (each wraps an agent's run method)
        workflow.add_node("memory", self._run_memory)
        workflow.add_node("planner", self._run_planner)
        workflow.add_node("retriever", self._run_retriever)
        workflow.add_node("sql_agent", self._run_sql)
        workflow.add_node("vision", self._run_vision)
        workflow.add_node("graph", self._run_graph)
        workflow.add_node("reasoning", self._run_reasoning)
        workflow.add_node("critic", self._run_critic)
        workflow.add_node("fact_checker", self._run_fact_checker)
        workflow.add_node("report_generator", self._run_report)

        # Define edges
        workflow.set_entry_point("memory")
        workflow.add_edge("memory", "planner")
        workflow.add_conditional_edges(
            "planner",
            self._route_after_planning,
            {
                "retriever": "retriever",
                "sql_agent": "sql_agent",
                "both": "retriever",
            },
        )

        # After retriever, check if SQL is also needed
        workflow.add_conditional_edges(
            "retriever",
            self._route_after_retrieval,
            {
                "sql_agent": "sql_agent",
                "vision": "vision",
                "graph": "graph",
                "reasoning": "reasoning",
            },
        )

        # After SQL, check for vision/graph or go to reasoning
        workflow.add_conditional_edges(
            "sql_agent",
            self._route_after_sql,
            {
                "vision": "vision",
                "graph": "graph",
                "reasoning": "reasoning",
            },
        )

        # Vision and Graph always lead to reasoning
        workflow.add_edge("vision", "graph")
        workflow.add_edge("graph", "reasoning")

        # Reasoning → Critic → Fact Checker → Report
        workflow.add_edge("reasoning", "critic")

        # Critic decides: pass → fact_checker, fail → reasoning (retry)
        workflow.add_conditional_edges(
            "critic",
            self._route_after_critic,
            {
                "fact_checker": "fact_checker",
                "reasoning": "reasoning",
                "report_generator": "report_generator",
            },
        )

        workflow.add_edge("fact_checker", "report_generator")
        workflow.add_edge("report_generator", END)

        return workflow.compile()

    # === Node execution wrappers ===

    async def _run_memory(self, state: AgentState) -> AgentState:
        return await self.memory_agent.run(dict(state))

    async def _run_planner(self, state: AgentState) -> AgentState:
        return await self.planner.run(dict(state))

    async def _run_retriever(self, state: AgentState) -> AgentState:
        return await self.retriever.run(dict(state))

    async def _run_sql(self, state: AgentState) -> AgentState:
        return await self.sql_agent.run(dict(state))

    async def _run_vision(self, state: AgentState) -> AgentState:
        return await self.vision_agent.run(dict(state))

    async def _run_graph(self, state: AgentState) -> AgentState:
        return await self.graph_agent.run(dict(state))

    async def _run_reasoning(self, state: AgentState) -> AgentState:
        return await self.reasoning_agent.run(dict(state))

    async def _run_critic(self, state: AgentState) -> AgentState:
        return await self.critic_agent.run(dict(state))

    async def _run_fact_checker(self, state: AgentState) -> AgentState:
        return await self.fact_checker.run(dict(state))

    async def _run_report(self, state: AgentState) -> AgentState:
        return await self.report_generator.run(dict(state))

    # === Routing functions ===

    def _route_after_planning(self, state: AgentState) -> str:
        """Route based on what agents the planner selected."""
        sub_tasks = state.get("sub_tasks", [])
        agents_needed = {t.get("agent", "").upper() for t in sub_tasks}

        has_retriever = "RETRIEVER" in agents_needed
        has_sql = "SQL_AGENT" in agents_needed

        if has_retriever and has_sql:
            return "both"  # Start with retriever, then SQL
        elif has_sql:
            return "sql_agent"
        else:
            return "retriever"  # Default to retriever

    def _route_after_retrieval(self, state: AgentState) -> str:
        """Route after retrieval completes."""
        sub_tasks = state.get("sub_tasks", [])
        agents_needed = {t.get("agent", "").upper() for t in sub_tasks}

        if "SQL_AGENT" in agents_needed and not state.get("sql_results"):
            return "sql_agent"
        elif "VISION" in agents_needed:
            return "vision"
        elif "GRAPH" in agents_needed:
            return "graph"
        else:
            return "reasoning"

    def _route_after_sql(self, state: AgentState) -> str:
        """Route after SQL completes."""
        sub_tasks = state.get("sub_tasks", [])
        agents_needed = {t.get("agent", "").upper() for t in sub_tasks}

        if "VISION" in agents_needed:
            return "vision"
        elif "GRAPH" in agents_needed:
            return "graph"
        else:
            return "reasoning"

    def _route_after_critic(self, state: AgentState) -> str:
        """Route based on critic evaluation."""
        critic_result = state.get("critic_result", {})
        retry_count = state.get("retry_count", 0)

        if critic_result.get("passed", True):
            return "fact_checker"
        elif retry_count < 1:
            # Allow one retry
            state["retry_count"] = retry_count + 1
            return "reasoning"
        else:
            # Skip fact check if already retried
            return "report_generator"

    # === Main execution ===

    async def run(
        self,
        query: str,
        user_id: int = 0,
        conversation_id: int = 0,
        image_paths: list = None,
    ) -> dict:
        """
        Execute the full multi-agent workflow.

        Args:
            query: User's question
            user_id: User ID for memory
            conversation_id: Conversation ID for context
            image_paths: Optional list of image file paths

        Returns:
            Final state with response, citations, and agent trace
        """
        start_time = time.time()

        initial_state: AgentState = {
            "query": query,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "image_paths": image_paths or [],
            "agent_trace": [],
            "retry_count": 0,
        }

        logger.info(f"Orchestrator starting for query: {query[:100]}...")

        try:
            # Execute the workflow
            final_state = await self.workflow.ainvoke(initial_state)

            total_ms = int((time.time() - start_time) * 1000)

            result = {
                "response": final_state.get("final_response", "Unable to generate response."),
                "confidence_score": final_state.get("confidence_score", 0),
                "citations": final_state.get("citations", []),
                "agent_trace": final_state.get("agent_trace", []),
                "quality_score": final_state.get("quality_score", 0),
                "faithfulness_score": final_state.get("faithfulness_score", 0),
                "latency_ms": total_ms,
                "plan": final_state.get("plan", {}),
            }

            logger.info(
                f"Orchestrator completed in {total_ms}ms. "
                f"Confidence: {result['confidence_score']:.2f}"
            )

            return result

        except Exception as e:
            total_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Orchestrator failed after {total_ms}ms: {e}")
            return {
                "response": f"I encountered an error while processing your question: {str(e)}",
                "confidence_score": 0,
                "citations": [],
                "agent_trace": initial_state.get("agent_trace", []),
                "latency_ms": total_ms,
                "error": str(e),
            }
