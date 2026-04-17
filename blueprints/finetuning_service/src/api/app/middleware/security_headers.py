"""
Security headers middleware — adds production-grade HTTP security headers to all responses.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable


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
