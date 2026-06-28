"""
EKOS Custom Exception Classes
Provides structured error handling across all modules.
"""

from typing import Any, Optional


class EKOSBaseError(Exception):
    """Base exception for all EKOS errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "EKOS_ERROR",
        details: Optional[dict[str, Any]] = None,
        status_code: int = 500,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# === Authentication Errors ===

class AuthenticationError(EKOSBaseError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message=message,
            error_code="AUTH_ERROR",
            status_code=401,
            **kwargs,
        )


class AuthorizationError(EKOSBaseError):
    """Raised when user lacks required permissions."""

    def __init__(self, message: str = "Insufficient permissions", **kwargs):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
            **kwargs,
        )


# === Document Errors ===

class DocumentNotFoundError(EKOSBaseError):
    """Raised when a document is not found."""

    def __init__(self, document_id: int, **kwargs):
        super().__init__(
            message=f"Document with ID {document_id} not found",
            error_code="DOCUMENT_NOT_FOUND",
            status_code=404,
            details={"document_id": document_id},
            **kwargs,
        )


class IngestionError(EKOSBaseError):
    """Raised when document ingestion fails."""

    def __init__(self, message: str, filename: str = "", **kwargs):
        super().__init__(
            message=message,
            error_code="INGESTION_ERROR",
            status_code=422,
            details={"filename": filename},
            **kwargs,
        )


class UnsupportedFileTypeError(EKOSBaseError):
    """Raised when an unsupported file type is uploaded."""

    def __init__(self, file_type: str, **kwargs):
        super().__init__(
            message=f"File type '{file_type}' is not supported",
            error_code="UNSUPPORTED_FILE_TYPE",
            status_code=415,
            details={"file_type": file_type},
            **kwargs,
        )


# === Agent Errors ===

class AgentExecutionError(EKOSBaseError):
    """Raised when an agent fails to execute."""

    def __init__(self, agent_name: str, message: str = "", **kwargs):
        super().__init__(
            message=f"Agent '{agent_name}' failed: {message}",
            error_code="AGENT_EXECUTION_ERROR",
            status_code=500,
            details={"agent_name": agent_name},
            **kwargs,
        )


class AgentTimeoutError(EKOSBaseError):
    """Raised when an agent exceeds time limit."""

    def __init__(self, agent_name: str, timeout_seconds: float, **kwargs):
        super().__init__(
            message=f"Agent '{agent_name}' timed out after {timeout_seconds}s",
            error_code="AGENT_TIMEOUT",
            status_code=504,
            details={"agent_name": agent_name, "timeout_seconds": timeout_seconds},
            **kwargs,
        )


# === LLM Errors ===

class LLMError(EKOSBaseError):
    """Raised when LLM API call fails."""

    def __init__(self, message: str = "LLM API call failed", **kwargs):
        super().__init__(
            message=message,
            error_code="LLM_ERROR",
            status_code=502,
            **kwargs,
        )


class RateLimitError(EKOSBaseError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", **kwargs):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            **kwargs,
        )


# === Database Errors ===

class DatabaseError(EKOSBaseError):
    """Raised when database operation fails."""

    def __init__(self, message: str = "Database operation failed", **kwargs):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            **kwargs,
        )


# === Retrieval Errors ===

class RetrievalError(EKOSBaseError):
    """Raised when retrieval pipeline fails."""

    def __init__(self, message: str = "Retrieval failed", **kwargs):
        super().__init__(
            message=message,
            error_code="RETRIEVAL_ERROR",
            status_code=500,
            **kwargs,
        )


# === Prompt Guard Errors ===

class PromptInjectionError(EKOSBaseError):
    """Raised when prompt injection is detected."""

    def __init__(self, message: str = "Potential prompt injection detected", **kwargs):
        super().__init__(
            message=message,
            error_code="PROMPT_INJECTION",
            status_code=400,
            **kwargs,
        )
