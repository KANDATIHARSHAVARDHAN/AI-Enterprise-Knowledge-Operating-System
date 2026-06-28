"""
EKOS Request Logger Middleware
Logs all incoming requests and responses with timing.
"""

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.utils.logger import logger


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Middleware that logs request/response details with timing."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Log incoming request
        logger.info(
            f"→ {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "extra_data": {
                    "method": request.method,
                    "path": str(request.url.path),
                    "query_params": str(request.query_params),
                },
            },
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"✗ {request.method} {request.url.path} - Error: {e}",
                extra={"request_id": request_id, "duration_ms": elapsed_ms},
            )
            raise

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Log response
        logger.info(
            f"← {request.method} {request.url.path} [{response.status_code}] {elapsed_ms}ms",
            extra={
                "request_id": request_id,
                "duration_ms": elapsed_ms,
                "extra_data": {"status_code": response.status_code},
            },
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms}ms"

        return response
