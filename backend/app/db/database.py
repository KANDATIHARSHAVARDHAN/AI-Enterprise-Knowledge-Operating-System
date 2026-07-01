"""
EKOS Database Engine & Session Management
Provides async SQLAlchemy engine and session factory for MySQL.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    
    def to_dict(self) -> dict:
        """Convert SQLAlchemy model instance to dict."""
        data = {}
        for col in self.__table__.columns:
            val = getattr(self, col.name)
            from decimal import Decimal
            from datetime import datetime
            if isinstance(val, Decimal):
                val = float(val)
            elif isinstance(val, datetime):
                # Convert to unix timestamp for consistency
                val = val.timestamp()
            data[col.name] = val
        return data



settings = get_settings()

# Conditional initialization based on database provider
if settings.database_provider != "firestore":
    # Async engine for MySQL
    engine = create_async_engine(
        settings.mysql_url,
        echo=settings.app_debug,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
    )

    # Session factory
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
else:
    engine = None
    async_session_factory = None


async def get_db():
    """Dependency that yields an async database session."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import AsyncFirestoreSession
        session = AsyncFirestoreSession()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    else:
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


async def init_db():
    """Create all tables (for development only)."""
    if settings.database_provider == "firestore":
        from app.db.firestore_db import get_firestore_client
        get_firestore_client()
    else:
        if engine:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Dispose of the engine connection pool."""
    if settings.database_provider != "firestore" and engine:
        await engine.dispose()
