"""
Authentication and authorization utilities for Keycloak OAuth2/OIDC
"""

import jwt
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

security = HTTPBearer()


class AuthManager:
    """Manages authentication with Keycloak OIDC"""

    def __init__(self, keycloak_issuer: str):
        """
        Initialize auth manager

        Args:
            keycloak_issuer: Keycloak issuer URL (e.g., https://domain.com/realms/myrealm)
        """
        self.keycloak_issuer = keycloak_issuer
        self.jwks_client: Optional[Any] = None

        if keycloak_issuer:
            try:
                from jwt import PyJWKClient
                jwks_url = f"{keycloak_issuer.rstrip('/')}/protocol/openid-connect/certs"
                self.jwks_client = PyJWKClient(jwks_url)
                logger.info(f"Initialized JWKS client for issuer: {keycloak_issuer}")
            except ImportError:
                logger.error("PyJWT with crypto support required. Install: pip install PyJWT[crypto]")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize JWKS client: {e}", exc_info=True)
                raise

    def extract_user_from_token(self, token: str) -> Dict[str, Any]:
        """
        Extract and validate user information from JWT token

        Args:
            token: JWT access token from Keycloak

        Returns:
            Dict with user information (user_id, email, username, token)

        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = None

            if self.jwks_client:
                try:
                    signing_key = self.jwks_client.get_signing_key_from_jwt(token)
                    payload = jwt.decode(
                        token,
                        signing_key.key,
                        algorithms=["RS256"],
                        # 'aud' is not always present in Keycloak tokens depending on
                        # client configuration, so audience verification is skipped here.
                        # Issuer (iss) is validated explicitly below instead.
                        options={"verify_aud": False},
                    )
                    # Validate issuer explicitly to prevent tokens from a different
                    # realm / identity provider being accepted.
                    token_iss = payload.get("iss", "")
                    expected_iss = self.keycloak_issuer.rstrip("/")
                    if token_iss.rstrip("/") != expected_iss:
                        logger.warning(
                            f"Token issuer mismatch: expected '{expected_iss}', got '{token_iss}'"
                        )
                        raise jwt.InvalidTokenError("Token issuer does not match configured issuer")
                    logger.debug("Successfully validated Keycloak token (signature + issuer)")
                except jwt.ExpiredSignatureError:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token has expired. Please log in again.",
                        headers={"WWW-Authenticate": "Bearer"}
                    )
                except jwt.InvalidTokenError as e:
                    logger.warning(f"Invalid token: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid authentication token",
                        headers={"WWW-Authenticate": "Bearer"}
                    )

            if not payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"}
                )

            # Check expiration manually as additional safety check
            exp = payload.get("exp", 0)
            if datetime.utcnow().timestamp() > exp:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"}
                )

            # Normalize user data from Keycloak token
            user_data = {
                "user_id": payload.get("sub"),  # Keycloak subject (user UUID)
                "email": payload.get("email"),
                "username": payload.get("preferred_username") or payload.get("username") or payload.get("email"),
                "token": token,
                "roles": payload.get("realm_access", {}).get("roles", []),
                "client_roles": payload.get("resource_access", {})
            }

            # Validate required fields
            if not user_data["user_id"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing user identifier",
                    headers={"WWW-Authenticate": "Bearer"}
                )

            return user_data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
                headers={"WWW-Authenticate": "Bearer"}
            )

    def has_role(self, user: Dict[str, Any], required_role: str) -> bool:
        """Check if user has a specific role"""
        return required_role in user.get("roles", [])

    def has_any_role(self, user: Dict[str, Any], required_roles: list) -> bool:
        """Check if user has any of the specified roles"""
        user_roles = set(user.get("roles", []))
        return bool(user_roles.intersection(set(required_roles)))


# Global auth manager instance (initialized in main.py)
auth_manager: Optional[AuthManager] = None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency to extract and validate current user from JWT token

    Usage:
        @app.get("/protected")
        async def protected_route(current_user: Dict = Depends(get_current_user)):
            return {"user_id": current_user["user_id"]}
    """
    if not auth_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication system not initialized"
        )

    token = credentials.credentials
    return auth_manager.extract_user_from_token(token)


async def require_role(required_role: str):
    """
    FastAPI dependency to require a specific role

    Usage:
        @app.post("/admin/endpoint")
        async def admin_only(
            current_user: Dict = Depends(get_current_user),
            _: None = Depends(require_role("admin"))
        ):
            ...
    """
    async def role_checker(current_user: Dict = Depends(get_current_user)):
        if not auth_manager:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication system not initialized"
            )

        if not auth_manager.has_role(current_user, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role}"
            )
        return None

    return role_checker
