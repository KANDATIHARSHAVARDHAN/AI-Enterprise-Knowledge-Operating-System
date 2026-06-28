"""
EKOS Rate Limiter Middleware
In-memory rate limiting per user/IP.
"""

import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.config import get_settings


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter."""

    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/api/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Identify client by IP
        client_ip = request.client.host if request.client else "unknown"
        key = client_ip

        now = time.time()
        window = self.settings.rate_limit_window_seconds
        max_requests = self.settings.rate_limit_requests

        # Clean old entries
        self._requests[key] = [
            ts for ts in self._requests[key] if now - ts < window
        ]

        if len(self._requests[key]) >= max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": f"Too many requests. Limit: {max_requests} per {window}s",
                    "retry_after": window,
                },
                headers={"Retry-After": str(window)},
            )

        self._requests[key].append(now)
        return await call_next(request)
