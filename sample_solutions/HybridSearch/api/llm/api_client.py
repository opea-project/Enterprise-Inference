"""
API Client for GenAI Gateway authentication and enterprise API calls
"""

import httpx
import logging
import re
from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)


def clean_url(url: str) -> str:
    """
    Remove invisible characters and whitespace from URL.

    Args:
        url (str): The URL string to clean.

    Returns:
        str: The cleaned URL string.
    """
    if not url:
        return url
    # Remove non-printable characters, whitespace, and specific zero-width chars
    return re.sub(r'[\x00-\x1f\x7f-\x9f\s\u200b\u2060\ufeff]+', '', url)


class APIClient:
    """
    Client for handling GenAI Gateway authentication and API calls.

    This client manages API calls to GenAI Gateway or APISIX Gateway endpoints,
    including LLM inference generation.
    """

    def __init__(self):
        # Use GenAI Gateway URL
        base_url = settings.genai_gateway_url
        self.base_url = clean_url(base_url).rstrip('/') if base_url else None
        self.token = settings.genai_api_key
        self.http_client = httpx.Client(verify=settings.verify_ssl, timeout=120.0) if self.token else None

        if not self.token or not self.base_url:
            raise ValueError("GenAI Gateway configuration missing. Check GENAI_GATEWAY_URL and GENAI_API_KEY.")

        logger.info(f"Using GenAI Gateway at {self.base_url}")

    def get_inference_client(self, endpoint: str = None):
        """
        Get OpenAI-style client for inference/completions.

        Args:
            endpoint (str, optional): Specific model endpoint path (ignored for GenAI Gateway).

        Returns:
            OpenAI: An instantiated OpenAI client configured for the GenAI Gateway.
        """
        # Standard OpenAI format
        client_base_url = f"{self.base_url}/v1"
        logger.info(f"Creating OpenAI client with base_url: {client_base_url}")

        http_client = httpx.Client(verify=settings.verify_ssl, timeout=120.0)

        return OpenAI(
            api_key=self.token,
            base_url=client_base_url,
            http_client=http_client
        )

    def is_authenticated(self) -> bool:
        """
        Check if client is authenticated.

        Returns:
            bool: True if authenticated, False otherwise.
        """
        return bool(self.token and self.http_client)


# Global instance
_api_client = None


def get_api_client():
    """
    Get or create global API client instance.

    Returns:
        APIClient: The global singleton instance of APIClient.
    """
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client
