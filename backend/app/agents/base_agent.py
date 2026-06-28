"""
EKOS Base Agent
Abstract base class for all agents with common functionality.
"""

import time
from abc import ABC, abstractmethod
from app.utils.logger import logger
from app.utils.exceptions import AgentExecutionError, AgentTimeoutError


class BaseAgent(ABC):
    """Abstract base class for all EKOS agents."""

    def __init__(self, name: str, description: str = "", timeout_seconds: float = 60.0):
        self.name = name
        self.description = description
        self.timeout_seconds = timeout_seconds
        self._execution_count = 0
        self._total_latency_ms = 0

    @abstractmethod
    async def execute(self, state: dict) -> dict:
        """
        Execute the agent's main logic.

        Args:
            state: Current agent workflow state dict

        Returns:
            Updated state dict with agent results
        """
        pass

    async def run(self, state: dict) -> dict:
        """
        Run the agent with timing, error handling, and logging.

        Args:
            state: Current workflow state

        Returns:
            Updated state with agent results and trace info
        """
        start_time = time.time()
        self._execution_count += 1

        logger.info(
            f"Agent '{self.name}' starting execution #{self._execution_count}",
            extra={"agent_name": self.name},
        )

        try:
            result = await self.execute(state)

            elapsed_ms = int((time.time() - start_time) * 1000)
            self._total_latency_ms += elapsed_ms

            # Add trace information
            if "agent_trace" not in result:
                result["agent_trace"] = []

            result["agent_trace"].append({
                "agent": self.name,
                "status": "success",
                "latency_ms": elapsed_ms,
                "execution_number": self._execution_count,
            })

            logger.info(
                f"Agent '{self.name}' completed in {elapsed_ms}ms",
                extra={"agent_name": self.name, "duration_ms": elapsed_ms},
            )

            return result

        except AgentTimeoutError:
            raise
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Add failure trace
            if "agent_trace" not in state:
                state["agent_trace"] = []

            state["agent_trace"].append({
                "agent": self.name,
                "status": "failed",
                "error": str(e),
                "latency_ms": elapsed_ms,
            })

            logger.error(
                f"Agent '{self.name}' failed after {elapsed_ms}ms: {e}",
                extra={"agent_name": self.name},
            )

            raise AgentExecutionError(self.name, str(e))

    @property
    def avg_latency_ms(self) -> float:
        """Average execution latency in milliseconds."""
        if self._execution_count == 0:
            return 0
        return self._total_latency_ms / self._execution_count
