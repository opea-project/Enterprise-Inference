"""
Correlation ID middleware for request tracing
"""

import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..observability import get_logger

logger = get_logger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Add correlation IDs to requests for distributed tracing

    Correlation IDs help track requests across services and make
    debugging easier by linking related log entries.
    """

    async def dispatch(self, request: Request, call_next):
        """Add or extract correlation ID from request"""
        # Check if correlation ID exists in headers
        correlation_id = request.headers.get("X-Correlation-ID")

        # Generate new ID if not provided
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in request state for use in handlers
        request.state.correlation_id = correlation_id

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response
