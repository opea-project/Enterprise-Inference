"""
Rate limiting — SlowAPI limiter instance and the rate-limit-exceeded error handler.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from ..config import get_settings

settings = get_settings()

# Rate limiter instance with configurable default
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit.default}/minute"]
)


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
