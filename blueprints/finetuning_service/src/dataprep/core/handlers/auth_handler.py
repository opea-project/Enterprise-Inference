"""
Authentication utilities and OpenAPI security configuration
"""
import asyncio
import base64
import logging

from keycloak import KeycloakOpenID
from fastapi import HTTPException, Header
from typing import Optional
from fastapi.openapi.utils import get_openapi
from core.config import settings
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_keycloak_openid():
    """
    Get and cache KeycloakOpenID instance.
    """
    return KeycloakOpenID(
        server_url=settings.KEYCLOAK_URL,
        client_id=settings.KEYCLOAK_CLIENT_ID,
        realm_name=settings.KEYCLOAK_REALM,
        client_secret_key=settings.KEYCLOAK_CLIENT_SECRET,
        verify=settings.KEYCLOAK_VERIFY_SSL
    )


async def validate_keycloak_token(token: str) -> str:
    """
    Validate JWT token from Keycloak and extract user_id.
    Runs the synchronous python-keycloak introspect call in a thread-pool
    executor so the async event loop is never blocked.
    """
    try:
        keycloak_openid = get_keycloak_openid()

        # Off-load the blocking HTTP call to a worker thread
        loop = asyncio.get_event_loop()
        token_info = await loop.run_in_executor(
            None, keycloak_openid.introspect, token
        )

        # Check if token is active
        if not token_info.get("active"):
            raise HTTPException(
                status_code=401,
                detail="Token is not active or invalid"
            )

        # Extract user ID from 'sub' claim
        user_id = token_info.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: user_id not found"
            )

        return user_id

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Keycloak token introspection failed")
        raise HTTPException(
            status_code=401,
            detail="Token validation failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


def validate_base64_token(token: str) -> str:
    """
    Original base64 token validation (legacy).
    """
    try:
        decoded_bytes = base64.b64decode(token)
        user_id = decoded_bytes.decode('utf-8')
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: user_id is empty"
            )
        return user_id
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Base64 token decode failed")
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )


async def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    Extract and decode user_id from Bearer token.
    Supports both Keycloak JWT and legacy base64 tokens.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header is required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = parts[1]

    # Use Keycloak validation if enabled, otherwise fall back to base64
    if settings.KEYCLOAK_ENABLED:
        return await validate_keycloak_token(token)
    else:
        return validate_base64_token(token)


def configure_openapi_auth(app):
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.API_TITLE,
        version=settings.API_VERSION,
        description="File and Data Preparation Backend API's",
        routes=app.routes,
    )

    if settings.KEYCLOAK_ENABLED:
        # OAuth2 configuration for Keycloak
        openapi_schema["components"]["securitySchemes"] = {
            "OAuth2": {
                "type": "oauth2",
                "flows": {
                    "password": {
                        "tokenUrl": f"{settings.keycloak_realm_url}/protocol/openid-connect/token",
                        "scopes": {}
                    },
                    "authorizationCode": {
                        "authorizationUrl": f"{settings.keycloak_realm_url}/protocol/openid-connect/auth",
                        "tokenUrl": f"{settings.keycloak_realm_url}/protocol/openid-connect/token",
                        "scopes": {}
                    }
                }
            }
        }
        openapi_schema["security"] = [{"OAuth2": []}]
    else:
        # Legacy base64 bearer auth
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "base64",
                "description": "Enter your base64 encoded user ID (e.g., 'ZmluZXR1bmluZy11c2Vy' for user 'finetuning-user')"
            }
        }
        openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema
