"""
API Client for GenAI Gateway authentication and enterprise API calls (Retrieval Service)
"""

import httpx
import logging
import re
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

    Specialized for the Retrieval Service to handle authentication for
    enterprise reranking endpoints.
    """

    def __init__(self):
        # Use per-model endpoint if set (APISIX), otherwise fall back to GenAI Gateway URL
        base_url = settings.reranker_api_endpoint or settings.genai_gateway_url
        self.base_url = clean_url(base_url).rstrip('/') if base_url else None
        self.token = settings.genai_api_key
        self.http_client = httpx.Client(verify=settings.verify_ssl, timeout=60.0) if self.token else None

        if self.token and self.base_url:
            logger.info(f"Using gateway at {self.base_url}")

    def get_rerank_client(self):
        """
        Get info for reranking client.

        Returns:
            tuple: (client_base_url, token)
        """
        if not self.token or not self.base_url:
            raise ValueError("GenAI Gateway configuration missing. Check GENAI_GATEWAY_URL and GENAI_API_KEY.")

        client_base_url = f"{self.base_url}"
        return client_base_url, self.token

    def rerank_pairs(self, query: str, docs: list[str]) -> list[float]:
        """
        Perform reranking using the GenAI Gateway reranking endpoint.

        Args:
            query (str): The search query.
            docs (list[str]): List of document texts to rerank against the query.

        Returns:
            list[float]: List of relevance scores corresponding to the input docs.

        Raises:
            Exception: If the reranker API call fails.
        """
        if not self.token or not self.base_url:
            raise ValueError("GenAI Gateway configuration missing. Check GENAI_GATEWAY_URL and GENAI_API_KEY.")

        url = f"{self.base_url}/rerank"

        payload = {
            "model": settings.reranker_model_name,
            "query": query,
            "documents": docs,
            "top_n": len(docs),
            "return_documents": False
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        if not self.http_client:
            self.http_client = httpx.Client(verify=settings.verify_ssl, timeout=60.0)

        response = self.http_client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            logger.error(f"Reranker API error: {response.status_code} - {response.text}")
            response.raise_for_status()

        # Expected format: {"results": [{"index": 0, "relevance_score": 0.9}, ...]}
        results = response.json().get("results", [])
        # Reconstruct scores in input order
        scores = [0.0] * len(docs)
        for res in results:
            scores[res["index"]] = res["relevance_score"]

        return scores

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
