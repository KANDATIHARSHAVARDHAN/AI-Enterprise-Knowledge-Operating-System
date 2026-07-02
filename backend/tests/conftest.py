"""
EKOS Test Fixtures
Configures pytest, DB engine, and mock clients for testing.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock
from app.db.models import User
from app.security.auth import hash_password

# Use in-memory SQLite for testing to avoid hitting local MySQL database during tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"  # Wait, SQLite doesn't use aiomysql. Let's use SQLite in-memory standard async:
# Actually, standard sqlite async is: sqlite+aiosqlite:///:memory:
# Let's use sqlite+aiosqlite for testing, but wait, the project uses MySQL.
# To keep it extremely simple, let's mock the database session or use a mock database.
# Let's define the engine. If we use sqlite+aiosqlite, we need aiosqlite installed. It's not in requirements.txt.
# Let's mock the db session or use a simple mock class for db operations,
# or create a mock database session fixture that doesn't actually hit a DB but returns mock results.
# Let's write standard pytest fixtures that mock AsyncSession.


@pytest.fixture
def mock_db() -> MagicMock:
    """Mock database session."""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock()
    return session


@pytest.fixture
def mock_user() -> User:
    """Mock active user."""
    return User(
        id=1,
        email="test@ekos.local",
        username="testuser",
        password_hash=hash_password("password123"),
        role="admin",
        is_active=True,
    )


@pytest.fixture
def mock_groq(monkeypatch) -> AsyncMock:
    """Mock Groq client and LangChain ChatGroq model."""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(return_value='{"query_understanding": "test", "sub_tasks": []}')
    mock_client.chat_with_fast_model = AsyncMock(return_value='{"score": 0.95}')

    import app.llm.groq_client
    monkeypatch.setattr(app.llm.groq_client, "_groq_client", mock_client)

    from langchain_core.messages import AIMessage
    from langchain_core.runnables import Runnable

    class MockChatModel(Runnable):
        def __init__(self, *args, **kwargs):
            pass

        def invoke(self, input_data, config=None, **kwargs):
            # Sync fallback (if needed)
            return AIMessage(content="mocked")

        async def ainvoke(self, input_data, config=None, **kwargs):
            # Await the mock chat method to respect test overrides
            content = await mock_client.chat()
            return AIMessage(content=content)

        def __or__(self, other):
            return self

    monkeypatch.setattr(app.llm.groq_client, "ChatGroq", MockChatModel)
    return mock_client


@pytest.fixture
def mock_embedder(monkeypatch) -> MagicMock:
    """Mock Document Embedder."""
    mock_client = MagicMock()
    mock_client.embed_text = MagicMock(return_value=[0.1] * 768)
    mock_client.embed_query = MagicMock(return_value=[0.1] * 768)
    mock_client.embed_batch = MagicMock(return_value=[[0.1] * 768])
    mock_client.dimension = 768

    import app.ingestion.embedder
    monkeypatch.setattr(app.ingestion.embedder, "_embedder", mock_client)
    return mock_client
