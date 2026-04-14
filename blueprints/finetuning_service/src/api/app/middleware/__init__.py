"""
Middleware package — re-exports all middleware components.

Individual modules:
  security_headers  — SecurityHeadersMiddleware (HTTP security headers + CSP)
  request_logging   — RequestLoggingMiddleware  (per-request timing + audit log)
  rate_limit        — limiter, rate_limit_exceeded_handler (SlowAPI)
  correlation       — CorrelationIDMiddleware   (distributed tracing IDs)
"""

from .security_headers import SecurityHeadersMiddleware
from .request_logging import RequestLoggingMiddleware
from .rate_limit import limiter, rate_limit_exceeded_handler
from .correlation import CorrelationIDMiddleware

__all__ = [
    "SecurityHeadersMiddleware",
    "RequestLoggingMiddleware",
    "limiter",
    "rate_limit_exceeded_handler",
    "CorrelationIDMiddleware",
]
