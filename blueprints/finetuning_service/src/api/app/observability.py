"""
Observability: Lightweight metrics and structured logging

Provides:
- Prometheus metrics for user tracking and API monitoring
- Structured JSON logging with request context
- Configurable via environment variables
- Minimal overhead (~5-10MB per pod)

User Tracking Metrics:
- api_requests_total: Count requests by user, endpoint, method, status
- api_request_duration_seconds: Response times by user and endpoint
- api_errors_total: Errors by user and error type
- active_jobs_by_user: Current job count per user
"""

import logging
import time
import psutil
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import structlog

from .config import get_settings

settings = get_settings()

# ============================================================================
# Structured Logging Configuration
# ============================================================================

def configure_logging():
    """Configure structured JSON logging with request context"""
    if not settings.observability.enabled:
        return

    if settings.observability.json_logs:
        # Production: JSON structured logs
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )
    else:
        # Development: Human-readable console logs
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                structlog.processors.TimeStamper(fmt="iso", utc=False),
                structlog.dev.ConsoleRenderer()
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )

def get_logger(name: str = __name__):
    """Get a structured logger instance"""
    if settings.observability.enabled:
        return structlog.get_logger(name)
    else:
        return logging.getLogger(name)


# ============================================================================
# Prometheus Metrics - User Tracking
# ============================================================================

# Request metrics with user tracking
api_requests_total = Counter(
    'api_requests_total',
    'Total API requests',
    ['user_id', 'endpoint', 'method', 'status_code']
)

api_request_duration_seconds = Histogram(
    'api_request_duration_seconds',
    'API request duration in seconds',
    ['user_id', 'endpoint', 'method'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Error tracking
api_errors_total = Counter(
    'api_errors_total',
    'Total API errors',
    ['user_id', 'endpoint', 'error_type']
)

# Job metrics per user
active_jobs_by_user = Gauge(
    'active_jobs_by_user',
    'Number of active jobs per user',
    ['user_id']
)

job_operations_total = Counter(
    'job_operations_total',
    'Total job operations',
    ['user_id', 'operation', 'status']  # operation: create, cancel, retrieve
)

# System metrics
system_cpu_percent = Gauge('system_cpu_percent', 'System CPU usage percentage')
system_memory_percent = Gauge('system_memory_percent', 'System memory usage percentage')
system_memory_bytes = Gauge('system_memory_bytes', 'System memory used in bytes')


# ============================================================================
# Metrics Middleware
# ============================================================================

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Track API requests with user identification

    Extracts user from OAuth token and records:
    - Request count per user/endpoint
    - Response times per user/endpoint
    - Error rates per user
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.observability.enabled:
            return await call_next(request)

        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        # Extract user from request
        user_id = self._extract_user_id(request)
        endpoint = self._normalize_endpoint(request.url.path)
        method = request.method

        # Start timing
        start_time = time.time()

        # Create structured logger with context
        logger = get_logger(__name__)
        logger = logger.bind(
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            path=request.url.path
        )

        try:
            # Process request
            response = await call_next(request)

            # Record metrics
            duration = time.time() - start_time
            status_code = response.status_code

            api_requests_total.labels(
                user_id=user_id,
                endpoint=endpoint,
                method=method,
                status_code=status_code
            ).inc()

            api_request_duration_seconds.labels(
                user_id=user_id,
                endpoint=endpoint,
                method=method
            ).observe(duration)

            # Log request
            logger.info(
                "request_completed",
                status_code=status_code,
                duration_seconds=round(duration, 4)
            )

            return response

        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__

            # Record error metrics
            api_errors_total.labels(
                user_id=user_id,
                endpoint=endpoint,
                error_type=error_type
            ).inc()

            api_requests_total.labels(
                user_id=user_id,
                endpoint=endpoint,
                method=method,
                status_code=500
            ).inc()

            # Log error
            logger.error(
                "request_failed",
                error_type=error_type,
                error_message=str(e),
                duration_seconds=round(duration, 4)
            )

            raise

    def _extract_user_id(self, request: Request) -> str:
        """
        Extract user ID from OAuth token

        Priority:
        1. JWT 'preferred_username' (Keycloak username - most readable)
        2. JWT 'sub' claim (Keycloak user ID/UUID)
        3. 'authenticated' if token exists but not decoded
        4. 'anonymous' if not authenticated
        """
        try:
            # Get user from request state (set by auth middleware)
            user = getattr(request.state, 'user', None)
            if user:
                # User is a dict with JWT claims
                return user.get('preferred_username') or user.get('sub') or 'anonymous'

            # Try to decode token directly (for requests that don't use get_current_user)
            auth_header = request.headers.get('authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.replace('Bearer ', '')
                try:
                    # Quick decode without verification to get username
                    import jwt
                    payload = jwt.decode(token, options={"verify_signature": False})
                    username = payload.get('preferred_username') or payload.get('sub')
                    if username:
                        return username
                except Exception:
                    pass
                # Token exists but couldn't decode
                return 'authenticated'

            return 'anonymous'

        except Exception:
            return 'unknown'

    def _normalize_endpoint(self, path: str) -> str:
        """
        Normalize endpoint path for metrics

        Replace dynamic IDs with {id} to avoid high cardinality
        Example: /v1/fine_tuning/jobs/job_123 -> /v1/fine_tuning/jobs/{job_id}
        """
        # Remove base path
        if path.startswith(settings.api.base_path):
            path = path[len(settings.api.base_path):]

        # Normalize job IDs
        parts = path.split('/')
        normalized = []
        for i, part in enumerate(parts):
            if i > 0 and parts[i-1] == 'jobs' and part.startswith(('job_', 'ftjob-')):
                normalized.append('{job_id}')
            elif i > 0 and parts[i-1] == 'models' and part:
                normalized.append('{model_id}')
            else:
                normalized.append(part)

        return '/'.join(normalized)


# ============================================================================
# System Metrics Collection
# ============================================================================

def update_system_metrics():
    """Update system resource metrics"""
    if not settings.observability.enabled:
        return

    try:
        system_cpu_percent.set(psutil.cpu_percent(interval=None))

        memory = psutil.virtual_memory()
        system_memory_percent.set(memory.percent)
        system_memory_bytes.set(memory.used)
    except Exception as e:
        logger = get_logger(__name__)
        logger.warning("failed_to_collect_system_metrics", error=str(e))


# ============================================================================
# Job Tracking Functions
# ============================================================================

def track_job_created(user_id: str):
    """Track when user creates a job"""
    if not settings.observability.enabled:
        return

    job_operations_total.labels(
        user_id=user_id,
        operation='create',
        status='success'
    ).inc()

    active_jobs_by_user.labels(user_id=user_id).inc()


def track_job_completed(user_id: str):
    """Track when user's job completes"""
    if not settings.observability.enabled:
        return

    active_jobs_by_user.labels(user_id=user_id).dec()


def track_job_cancelled(user_id: str):
    """Track when user cancels a job"""
    if not settings.observability.enabled:
        return

    job_operations_total.labels(
        user_id=user_id,
        operation='cancel',
        status='success'
    ).inc()

    active_jobs_by_user.labels(user_id=user_id).dec()


# ============================================================================
# Metrics Endpoint
# ============================================================================

async def metrics_endpoint(request: Request):
    """
    Prometheus metrics endpoint

    Returns:
        Prometheus-formatted metrics for scraping

    Example queries:
        # Total requests per user
        sum by (user_id) (api_requests_total)

        # Average response time per user
        rate(api_request_duration_seconds_sum[5m]) / rate(api_request_duration_seconds_count[5m])

        # Requests per user per endpoint
        sum by (user_id, endpoint) (api_requests_total)

        # Error rate per user
        sum by (user_id) (api_errors_total)
    """
    # Update system metrics before exposing
    update_system_metrics()

    # Return Prometheus-formatted metrics
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
