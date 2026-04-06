# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from fastapi import HTTPException, Depends, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from functools import lru_cache
import httpx
from jose import jwt, JWTError

from app.config import settings

# -------------------------------------------------------------------
# OAuth2 / Keycloak Authentication (Bearer JWT)
# -------------------------------------------------------------------

bearer_scheme = HTTPBearer(auto_error=True)


@lru_cache()
def get_keycloak_jwks():
    """Fetch and cache Keycloak JWKS (JSON Web Key Set) for token validation.

    Uses KEYCLOAK_INTERNAL_URL when set (container-to-container inside Docker)
    so that the fetch goes through the internal network instead of the
    external hostname, which may not be reachable from within the container.
    The JWT `iss` claim is still validated against the public KEYCLOAK_ISSUER.
    """
    base = settings.KEYCLOAK_INTERNAL_URL or settings.KEYCLOAK_ISSUER
    jwks_url = f"{base}/protocol/openid-connect/certs"
    response = httpx.get(jwks_url, timeout=10, verify=settings.KEYCLOAK_TLS_VERIFY)
    response.raise_for_status()
    return response.json()


async def verify_access_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Validate Keycloak-issued JWT Bearer token."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    token = credentials.credentials

    try:
        # Select the matching JWK by the kid in the token header.
        # python-jose jwt.decode() expects a single JWK dict, not the full JWKS.
        jwks = get_keycloak_jwks()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
        key = next((k for k in keys if k.get("kid") == kid), None)
        if key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find matching JWK for token kid",
            )

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.KEYCLOAK_ISSUER,
            options={
                "verify_aud": False,
            },
        )

        if payload.get("azp") != settings.KEYCLOAK_AUDIENCE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token audience",
            )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )


async def get_files_api_token(ft_api_key: Optional[str] = Header(None)) -> str:
    """
    Extract the FILES API bearer token from the ft-api-key header.

    This token is provided by the client and used to authenticate with the
    FILES API service for downloading datasets and uploading models.

    Args:
        ft_api_key: Bearer token passed via ft-api-key header

    Returns:
        Bearer token string

    Raises:
        HTTPException: If token is missing
    """
    if not ft_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing ft-api-key header. This header must contain the FILES API bearer token.",
        )
    return ft_api_key
