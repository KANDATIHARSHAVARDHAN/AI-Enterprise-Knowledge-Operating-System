"""
EKOS Memory Agent
Manages conversation context and long-term memory.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.base_agent import BaseAgent
from app.db.models import Message, Conversation, MemoryStore
from app.utils.logger import logger


class MemoryAgent(BaseAgent):
    """Manages short-term and long-term conversation memory."""

    def __init__(self, db_session: AsyncSession = None):
        super().__init__(
            name="memory_agent",
            description="Manages conversation context and long-term memory",
        )
        self.db_session = db_session

    async def execute(self, state: dict) -> dict:
        """Retrieve and update conversation memory."""
        user_id = state.get("user_id")
        conversation_id = state.get("conversation_id")
        query = state.get("query", "")

        memory_context = {
            "conversation_history": [],
            "relevant_memories": [],
        }

        if self.db_session and conversation_id:
            # Get recent conversation history
            memory_context["conversation_history"] = await self._get_conversation_history(
                conversation_id, limit=10
            )

        if self.db_session and user_id:
            # Get relevant long-term memories
            memory_context["relevant_memories"] = await self._get_relevant_memories(
                user_id, query
            )

        # Format context for other agents
        history_text = ""
        for msg in memory_context["conversation_history"]:
            history_text += f"{msg['role'].upper()}: {msg['content'][:200]}\n"

        memory_text = ""
        for mem in memory_context["relevant_memories"]:
            memory_text += f"[Memory] {mem['content'][:200]}\n"

        state["conversation_context"] = history_text or "No previous context."
        state["memory_context"] = memory_text
        state["memory_data"] = memory_context

        logger.info(
            f"Memory Agent: {len(memory_context['conversation_history'])} history messages, "
            f"{len(memory_context['relevant_memories'])} memories"
        )
        return state

    async def _get_conversation_history(
        self, conversation_id: int, limit: int = 10
    ) -> list[dict]:
        """Get recent messages from the conversation."""
        try:
            result = await self.db_session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(desc(Message.created_at))
                .limit(limit)
            )
            messages = result.scalars().all()
            return [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else "",
                }
                for msg in reversed(messages)
            ]
        except Exception as e:
            logger.warning(f"Failed to get conversation history: {e}")
            return []

    async def _get_relevant_memories(
        self, user_id: int, query: str, limit: int = 5
    ) -> list[dict]:
        """Get relevant long-term memories for the user."""
        try:
            result = await self.db_session.execute(
                select(MemoryStore)
                .where(MemoryStore.user_id == user_id)
                .order_by(desc(MemoryStore.importance_score))
                .limit(limit)
            )
            memories = result.scalars().all()
            return [
                {
                    "type": mem.memory_type,
                    "content": mem.content,
                    "importance": mem.importance_score,
                }
                for mem in memories
            ]
        except Exception as e:
            logger.warning(f"Failed to get memories: {e}")
            return []

    async def store_memory(
        self, user_id: int, content: str, memory_type: str = "fact", importance: float = 0.5
    ):
        """Store a new long-term memory."""
        if not self.db_session:
            return

        try:
            memory = MemoryStore(
                user_id=user_id,
                memory_type=memory_type,
                content=content,
                importance_score=importance,
            )
            self.db_session.add(memory)
            await self.db_session.flush()
            logger.info(f"Stored memory for user {user_id}: {content[:50]}...")
        except Exception as e:
            logger.warning(f"Failed to store memory: {e}")
