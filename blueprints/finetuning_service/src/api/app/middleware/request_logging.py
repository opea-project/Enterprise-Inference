"""
Request logging middleware — logs all incoming requests with timing and sanitises sensitive headers.
"""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with timing and sanitize sensitive data"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # Log incoming request (sanitize auth headers)
        headers = dict(request.headers)
        if "authorization" in headers:
            headers["authorization"] = "Bearer [REDACTED]"

        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else None
            }
        )

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            logger.info(
                f"Response: {response.status_code} in {process_time:.3f}s",
                extra={
                    "status_code": response.status_code,
                    "duration_seconds": process_time,
                    "path": request.url.path
                }
            )

            response.headers["X-Process-Time"] = str(process_time)
            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {str(e)} in {process_time:.3f}s",
                extra={
                    "error": str(e),
                    "duration_seconds": process_time,
                    "path": request.url.path
                },
                exc_info=True
            )
            raise
