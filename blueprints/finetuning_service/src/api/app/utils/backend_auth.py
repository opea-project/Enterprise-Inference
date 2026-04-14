"""
Generic Backend Authentication Module

Provides abstraction for authenticating with different training backends.
Each backend may use different authentication mechanisms:
- OAuth2 Client Credentials (Keycloak, Azure AD)
- API Keys
- Bearer tokens
- Custom authentication

This module is SEPARATE from user authentication (handled by app/auth.py).
"""

import httpx
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from threading import Lock

logger = logging.getLogger(__name__)


class BackendAuthProvider(ABC):
    """Abstract base class for backend authentication providers"""

    @abstractmethod
    async def get_auth_header(self) -> Dict[str, str]:
        """Get authentication header(s) for backend API requests"""
        pass

    @abstractmethod
    def invalidate(self) -> None:
        """Invalidate cached credentials (force refresh on next request)"""
        pass


class OAuth2ClientCredentialsAuth(BackendAuthProvider):
    """
    OAuth2 Client Credentials Flow Authentication

    Used by: Nvidia Keycloak, Azure AD, etc.
    Automatically refreshes tokens before expiration.
    Thread-safe for concurrent requests.
    """

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = None,
        refresh_buffer_seconds: int = 300,
        verify_ssl: bool = True,
        timeout: float = 30.0
    ):
        """
        Initialize OAuth2 client credentials authentication

        Args:
            token_url: OAuth2 token endpoint URL
            client_id: Client ID
            client_secret: Client secret
            scope: Optional scope (space-separated)
            refresh_buffer_seconds: Refresh token N seconds before expiry
            verify_ssl: Verify SSL certificates
            timeout: HTTP request timeout
        """
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.refresh_buffer_seconds = refresh_buffer_seconds
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        # Token cache
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._lock = Lock()

        logger.info(f"Initialized OAuth2 auth for {token_url}")

    def _is_token_valid(self) -> bool:
        """Check if cached token is valid"""
        if not self._access_token or not self._token_expiry:
            return False

        now = datetime.utcnow()
        buffer = timedelta(seconds=self.refresh_buffer_seconds)
        return self._token_expiry > (now + buffer)

    async def _fetch_token(self) -> Dict[str, Any]:
        """Fetch new access token from OAuth2 provider"""
        try:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }

            if self.scope:
                data["scope"] = self.scope

            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            async with httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_ssl
            ) as client:
                response = await client.post(
                    self.token_url,
                    data=data,
                    headers=headers
                )

                if response.status_code == 200:
                    token_data = response.json()
                    logger.debug("Successfully obtained OAuth2 access token")
                    return token_data
                else:
                    logger.error(f"OAuth2 token request failed: {response.status_code} - {response.text}")
                    raise Exception(f"OAuth2 token request failed with status code {response.status_code}")

        except httpx.TimeoutException:
            logger.error(f"Timeout requesting token from {self.token_url}")
            raise Exception("OAuth2 token request timeout")
        except Exception as e:
            logger.error(f"Error fetching OAuth2 token: {e}")
            raise

    async def get_token(self) -> str:
        """Get valid access token (fetches new if expired)"""
        with self._lock:
            if self._is_token_valid():
                return self._access_token

        # Token invalid, fetch new one
        token_data = await self._fetch_token()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)

        if not access_token:
            raise Exception("No access token in OAuth2 response")

        token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)

        with self._lock:
            self._access_token = access_token
            self._token_expiry = token_expiry

        logger.info(f"Token cached, expires at {token_expiry.isoformat()}")
        return access_token

    async def get_auth_header(self) -> Dict[str, str]:
        """Get Authorization header with Bearer token"""
        token = await self.get_token()
        return {"Authorization": f"Bearer {token}"}

    def invalidate(self) -> None:
        """Invalidate cached token (force refresh on next request)"""
        with self._lock:
            logger.info("Invalidating cached OAuth2 token")
            self._access_token = None
            self._token_expiry = None


class APIKeyAuth(BackendAuthProvider):
    """
    Simple API Key Authentication

    Used by: Custom backends with API key authentication
    """

    def __init__(self, api_key: str, header_name: str = "X-API-Key"):
        """
        Initialize API key authentication

        Args:
            api_key: The API key
            header_name: HTTP header name for the API key
        """
        self.api_key = api_key
        self.header_name = header_name

    async def get_auth_header(self) -> Dict[str, str]:
        """Get API key header"""
        return {self.header_name: self.api_key}

    def invalidate(self) -> None:
        """API keys don't need invalidation"""
        pass


class BearerTokenAuth(BackendAuthProvider):
    """
    Simple Bearer Token Authentication

    Used by: Backends with static bearer tokens
    """

    def __init__(self, token: str):
        """
        Initialize bearer token authentication

        Args:
            token: The bearer token
        """
        self.token = token

    async def get_auth_header(self) -> Dict[str, str]:
        """Get Authorization header with Bearer token"""
        return {"Authorization": f"Bearer {self.token}"}

    def invalidate(self) -> None:
        """Static tokens don't need invalidation"""
        pass


class NoAuth(BackendAuthProvider):
    """
    No Authentication

    Used by: Public or internally-secured backends
    """

    async def get_auth_header(self) -> Dict[str, str]:
        """Return empty headers"""
        return {}

    def invalidate(self) -> None:
        """Nothing to invalidate"""
        pass


def create_backend_auth(auth_config: Dict[str, Any]) -> BackendAuthProvider:
    """
    Factory function to create appropriate backend auth provider

    Args:
        auth_config: Authentication configuration dictionary

    Returns:
        BackendAuthProvider instance

    Example:
        # OAuth2
        auth = create_backend_auth({
            'type': 'oauth2_client_credentials',
            'token_url': 'https://...',
            'client_id': '...',
            'client_secret': '...'
        })

        # API Key
        auth = create_backend_auth({
            'type': 'api_key',
            'api_key': '...',
            'header_name': 'X-API-Key'
        })
    """
    auth_type = auth_config.get('type', 'none')

    if auth_type == 'oauth2_client_credentials':
        return OAuth2ClientCredentialsAuth(
            token_url=auth_config['token_url'],
            client_id=auth_config['client_id'],
            client_secret=auth_config['client_secret'],
            scope=auth_config.get('scope'),
            refresh_buffer_seconds=auth_config.get('refresh_buffer_seconds', 300),
            verify_ssl=auth_config.get('verify_ssl', True),
            timeout=auth_config.get('timeout', 30.0)
        )

    elif auth_type == 'api_key':
        return APIKeyAuth(
            api_key=auth_config['api_key'],
            header_name=auth_config.get('header_name', 'X-API-Key')
        )

    elif auth_type == 'bearer_token':
        return BearerTokenAuth(token=auth_config['token'])

    elif auth_type == 'none':
        return NoAuth()

    else:
        raise ValueError(f"Unsupported auth type: {auth_type}")
