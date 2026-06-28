"""
EKOS SQLAlchemy ORM Models
Maps all MySQL tables to Python classes.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    Enum, BigInteger, JSON, ForeignKey, DECIMAL, Index,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class User(Base):
    """User account model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), default="")
    role = Column(Enum("admin", "analyst", "viewer"), nullable=False, default="viewer")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    documents = relationship("Document", back_populates="uploader", lazy="selectin")
    conversations = relationship("Conversation", back_populates="user", lazy="selectin")
    query_logs = relationship("QueryLog", back_populates="user", lazy="selectin")
    memories = relationship("MemoryStore", back_populates="user", lazy="selectin")


class Document(Base):
    """Uploaded document model."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False, default=0)
    file_path = Column(String(1000), nullable=False)
    status = Column(
        Enum("pending", "processing", "completed", "failed"),
        nullable=False, default="pending"
    )
    error_message = Column(Text)
    chunk_count = Column(Integer, default=0)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    metadata_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    uploader = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Document chunk model for RAG."""
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    metadata_json = Column(JSON)
    embedding_id = Column(String(100))
    token_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("idx_chunks_doc_index", "document_id", "chunk_index", unique=True),
    )


class Conversation(Base):
    """Chat conversation model."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), default="New Conversation")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Chat message model."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum("user", "assistant", "system"), nullable=False)
    content = Column(Text, nullable=False)
    agent_trace_json = Column(JSON)
    citations_json = Column(JSON)
    confidence_score = Column(Float)
    latency_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class QueryLog(Base):
    """Query execution log for evaluation and monitoring."""
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="SET NULL"))
    query = Column(Text, nullable=False)
    response_summary = Column(Text)
    retrieved_chunks_json = Column(JSON)
    agent_path_json = Column(JSON)
    latency_ms = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    model_used = Column(String(100))
    status = Column(Enum("success", "failed", "partial"), default="success")
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="query_logs")
    evaluation_results = relationship("EvaluationResult", back_populates="query_log", cascade="all, delete-orphan")


class EvaluationResult(Base):
    """Evaluation metric result per query."""
    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_log_id = Column(Integer, ForeignKey("query_logs.id", ondelete="CASCADE"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    score = Column(Float, nullable=False)
    details_json = Column(JSON)
    evaluator = Column(String(50), default="ragas")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    query_log = relationship("QueryLog", back_populates="evaluation_results")


class MachineEvent(Base):
    """Enterprise sample data: machine events."""
    __tablename__ = "machine_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(String(50), nullable=False, index=True)
    machine_name = Column(String(200), nullable=False)
    event_type = Column(
        Enum("failure", "warning", "maintenance", "inspection", "repair"),
        nullable=False
    )
    description = Column(Text, nullable=False)
    severity = Column(Enum("critical", "high", "medium", "low"), nullable=False, default="medium")
    root_cause = Column(Text)
    reported_by = Column(String(200))
    department = Column(String(100))
    production_line = Column(String(100))
    downtime_hours = Column(Float, default=0)
    cost_usd = Column(DECIMAL(10, 2), default=0)
    event_date = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class MaintenanceLog(Base):
    """Enterprise sample data: maintenance logs."""
    __tablename__ = "maintenance_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(String(50), nullable=False, index=True)
    machine_name = Column(String(200), nullable=False)
    action_type = Column(
        Enum("preventive", "corrective", "emergency", "inspection"),
        nullable=False
    )
    description = Column(Text, nullable=False)
    technician = Column(String(200), nullable=False)
    parts_replaced = Column(Text)
    parts_cost_usd = Column(DECIMAL(10, 2), default=0)
    labor_cost_usd = Column(DECIMAL(10, 2), default=0)
    total_cost_usd = Column(DECIMAL(10, 2), default=0)
    duration_hours = Column(Float, default=0)
    status = Column(
        Enum("completed", "in_progress", "scheduled", "cancelled"),
        default="completed"
    )
    notes = Column(Text)
    log_date = Column(DateTime, nullable=False)
    next_maintenance_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Audit trail for security and compliance."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(String(100))
    details_json = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)


class MemoryStore(Base):
    """Long-term memory for conversation context."""
    __tablename__ = "memory_store"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    memory_type = Column(Enum("fact", "preference", "summary", "entity"), nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON)
    importance_score = Column(Float, default=0.5)
    access_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="memories")
