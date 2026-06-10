"""
API Client for inference API calls
"""

from enum import verify
import logging
import httpx
from typing import Optional
import config

logger = logging.getLogger(__name__)


class APIClient:
    """
    Client for handling inference API calls
    """

    def __init__(self):
        self.endpoint = config.INFERENCE_API_ENDPOINT
        self.token = config.INFERENCE_API_TOKEN
        self.http_client = httpx.Client(verify=config.VERIFY_SSL) if self.token else None

    def get_inference_client(self):
        """
        Get OpenAI-style client for code generation inference
        """
        from openai import OpenAI

        return OpenAI(
            api_key=self.token,
            base_url=f"{self.endpoint}/v1",
            http_client=self.http_client
        )

    def translate_code(self, source_code: str, source_lang: str, target_lang: str) -> str:
        """
        Translate code from one language to another using an instruct model.

        Args:
            source_code: Code to translate
            source_lang: Source programming language
            target_lang: Target programming language

        Returns:
            Translated code
        """
        try:
            client = self.get_inference_client()

            logger.info(f"Translating code from {source_lang} to {target_lang}")

            response = client.chat.completions.create(
                model=config.INFERENCE_MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are an expert code translator. "
                            f"Translate {source_lang} code to {target_lang}. "
                            f"Output only the translated code with no explanations or markdown."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Translate this {source_lang} code to {target_lang}:\n\n{source_code}",
                    },
                ],
                max_tokens=config.LLM_MAX_TOKENS,
                temperature=config.LLM_TEMPERATURE,
            )

            if response.choices:
                translated_code = response.choices[0].message.content.strip()
                # Strip markdown code fences if model wraps output anyway
                if translated_code.startswith("```"):
                    lines = translated_code.splitlines()
                    translated_code = "\n".join(
                        lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                    ).strip()
                logger.info(f"Successfully translated code ({len(translated_code)} characters)")
                return translated_code

            logger.error(f"Empty choices in response: {response}")
            return ""
        except Exception as e:
            logger.error(f"Error translating code: {str(e)}", exc_info=True)
            raise

    def is_authenticated(self) -> bool:
        """
        Check if client is authenticated
        """
        return self.token is not None

    def __del__(self):
        """
        Cleanup: close httpx client
        """
        if self.http_client:
            self.http_client.close()


# Global API client instance
_api_client: Optional[APIClient] = None


def get_api_client() -> APIClient:
    """
    Get or create the global API client instance

    Returns:
        APIClient instance
    """
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client
