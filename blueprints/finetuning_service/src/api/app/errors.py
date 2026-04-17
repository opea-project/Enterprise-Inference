"""
Centralized error handling and OpenAI-compatible error responses
"""

from typing import Optional, Dict, Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger(__name__)


class OpenAIError(Exception):
    """Base exception for OpenAI-compatible errors"""

    def __init__(
        self,
        message: str,
        error_type: str = "api_error",
        code: Optional[str] = None,
        param: Optional[str] = None,
        status_code: int = 500
    ):
        self.message = message
        self.error_type = error_type
        self.code = code
        self.param = param
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to OpenAI error format"""
        error_dict = {
            "message": self.message,
            "type": self.error_type
        }
        if self.code:
            error_dict["code"] = self.code
        if self.param:
            error_dict["param"] = self.param
        return {"error": error_dict}


class InvalidRequestError(OpenAIError):
    """Invalid request error (400)"""

    def __init__(self, message: str, code: Optional[str] = None, param: Optional[str] = None):
        super().__init__(
            message=message,
            error_type="invalid_request_error",
            code=code or "invalid_request",
            param=param,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class AuthenticationError(OpenAIError):
    """Authentication error (401)"""

    def __init__(self, message: str = "Invalid authentication credentials"):
        super().__init__(
            message=message,
            error_type="authentication_error",
            code="invalid_api_key",
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class PermissionError(OpenAIError):
    """Permission denied error (403)"""

    def __init__(self, message: str = "You do not have permission to access this resource"):
        super().__init__(
            message=message,
            error_type="permission_error",
            code="forbidden",
            status_code=status.HTTP_403_FORBIDDEN
        )


class ResourceNotFoundError(OpenAIError):
    """Resource not found error (404)"""

    def __init__(self, resource_type: str = "resource", resource_id: Optional[str] = None):
        message = f"The requested {resource_type} was not found"
        if resource_id:
            message += f": {resource_id}"
        super().__init__(
            message=message,
            error_type="invalid_request_error",
            code="not_found",
            status_code=status.HTTP_404_NOT_FOUND
        )


class RateLimitError(OpenAIError):
    """Rate limit exceeded error (429)"""

    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(
            message=message,
            error_type="rate_limit_error",
            code="rate_limit_exceeded",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )


class ServerError(OpenAIError):
    """Internal server error (500)"""

    def __init__(self, message: str = "An unexpected error occurred. Please try again later."):
        super().__init__(
            message=message,
            error_type="server_error",
            code="internal_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ServiceUnavailableError(OpenAIError):
    """Service unavailable error (503)"""

    def __init__(self, message: str = "The service is temporarily unavailable. Please try again later."):
        super().__init__(
            message=message,
            error_type="server_error",
            code="service_unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


def create_error_response(
    message: str,
    error_type: str = "api_error",
    code: Optional[str] = None,
    status_code: int = 500,
    param: Optional[str] = None
) -> JSONResponse:
    """Create an OpenAI-compatible error response"""
    error_content = {
        "error": {
            "message": message,
            "type": error_type
        }
    }

    if code:
        error_content["error"]["code"] = code
    if param:
        error_content["error"]["param"] = param

    return JSONResponse(
        status_code=status_code,
        content=error_content
    )


async def openai_error_exception_handler(request: Request, exc: OpenAIError) -> JSONResponse:
    """Exception handler for OpenAI-compatible errors"""
    logger.warning(
        f"OpenAI error: {exc.error_type} - {exc.message}",
        extra={
            "error_type": exc.error_type,
            "error_code": exc.code,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert FastAPI validation errors to OpenAI-compatible format"""
    # Extract and format validation errors
    errors = []
    for error in exc.errors():
        error_dict = {
            "loc": list(error.get("loc", [])),
            "msg": error.get("msg", ""),
            "type": error.get("type", "")
        }

        # Handle ctx which may contain non-serializable objects
        if "ctx" in error and error["ctx"]:
            ctx_serializable = {}
            for key, value in error["ctx"].items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    ctx_serializable[key] = value
                else:
                    ctx_serializable[key] = str(value)
            error_dict["ctx"] = ctx_serializable

        errors.append(error_dict)

    # Create user-friendly error message
    if errors:
        first_error = errors[0]
        field = ".".join(str(loc) for loc in first_error["loc"] if loc != "body")
        message = f"Invalid value for '{field}': {first_error['msg']}"
    else:
        message = "Invalid request parameters"

    logger.warning(
        f"Validation error: {message}",
        extra={
            "validation_errors": errors,
            "path": request.url.path
        }
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "code": "validation_error",
                "details": errors
            }
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler for unexpected errors"""
    logger.error(
        f"Unexpected error: {str(exc)}",
        extra={"path": request.url.path},
        exc_info=True
    )

    # Don't expose internal error details in production
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "An unexpected error occurred. Please try again later.",
                "type": "server_error",
                "code": "internal_error"
            }
        }
    )
