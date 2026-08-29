"""
API client abstraction layer.

Supports GenAI Gateway, APISIX Gateway, and any OpenAI-compatible inference endpoint.
"""

import logging
import httpx
from typing import Optional
from openai import OpenAI

import config

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass


class APIClient:
    """Unified API client for inference endpoints"""

    def __init__(self):
        if not config.INFERENCE_API_ENDPOINT:
            raise AuthenticationError("INFERENCE_API_ENDPOINT is required")

        if not config.INFERENCE_API_TOKEN:
            raise AuthenticationError("INFERENCE_API_TOKEN is required")

        self.base_url = config.INFERENCE_API_ENDPOINT
        self.api_key = config.INFERENCE_API_TOKEN

        # Configure httpx clients with extended timeouts for slower inference servers
        # Default httpx timeout is 5 seconds, which is too short for VL model inference
        timeout_config = httpx.Timeout(300.0, connect=60.0)  # 5 minutes read, 1 minute connect
        self.http_client = httpx.Client(verify=config.VERIFY_SSL, timeout=timeout_config)
        self.async_http_client = httpx.AsyncClient(verify=config.VERIFY_SSL, timeout=timeout_config)

        logger.info(f"Inference endpoint configured: {self.base_url}")

    def get_openai_client(self) -> OpenAI:
        return OpenAI(
            api_key=self.api_key,
            base_url=f"{self.base_url}/v1",
            http_client=self.http_client
        )

    def is_authenticated(self) -> bool:
        return bool(self.api_key)

    def __del__(self):
        """Cleanup HTTP clients on deletion"""
        if hasattr(self, 'http_client') and self.http_client:
            try:
                self.http_client.close()
            except Exception:
                pass
        if hasattr(self, 'async_http_client') and self.async_http_client:
            try:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.async_http_client.aclose())
                    else:
                        loop.run_until_complete(self.async_http_client.aclose())
                except RuntimeError:
                    pass
            except Exception:
                pass


_api_client: Optional[APIClient] = None


def get_api_client() -> APIClient:
    """
    Get or create global API client instance

    Returns:
        Configured API client

    Raises:
        AuthenticationError: If authentication configuration is invalid
    """
    global _api_client

    if _api_client is None:
        logger.info("Initializing API client")
        _api_client = APIClient()

    return _api_client
