"""
Middleware for security, rate limiting, and request/response handling
"""

import os

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)


"""
Shared rate limiter instance for all routes.
Uses slowapi (wrapper around limits library) with per-IP rate limiting.

Global default: 100 requests/minute (applied via SlowAPIMiddleware to all routes)
Upload endpoints: 10 requests/minute (stricter, set per-route)

Storage: Redis is used as the shared backend so that rate-limit counters are
aggregated correctly across multiple Uvicorn workers and Kubernetes pod replicas.
Falls back to in-memory storage only when CELERY_BROKER_URL is not configured
(e.g. local development without Redis).
"""
_redis_url: str = os.getenv("CELERY_BROKER_URL", "")
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri=_redis_url if _redis_url else None,
)



class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses with production-grade CSP"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers - Production grade
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # Content Security Policy - Allow necessary resources for Swagger UI
        # while maintaining security for production
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",  # Swagger UI scripts
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",   # Swagger UI styles
            "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.jsdelivr.net",  # Images and icons
            "font-src 'self' https://cdn.jsdelivr.net",  # Fonts
            "connect-src 'self'",  # API calls only to same origin
            "frame-ancestors 'none'",  # Prevent clickjacking
            "base-uri 'self'",  # Restrict base URL
            "form-action 'self'"  # Restrict form submissions
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        return response


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

            # Log response
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


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors (OpenAI-compatible)"""
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "message": "Rate limit exceeded. Please try again later.",
                "type": "rate_limit_error",
                "code": "rate_limit_exceeded"
            }
        }
    )