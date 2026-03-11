"""
LLM Service - Handles LLM initialization for inference endpoints
Supports GenAI Gateway, APISIX Gateway, and any OpenAI-compatible endpoint
"""

import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from config import settings

logger = logging.getLogger(__name__)


def get_llm(model_name: Optional[str] = None, temperature: float = 0.7) -> ChatOpenAI:
    """
    Get LLM instance configured for inference endpoint

    Args:
        model_name: Override model name (required - specify which agent model to use)
        temperature: Temperature for generation

    Returns:
        ChatOpenAI instance configured for the inference endpoint
    """
    if model_name is None:
        raise ValueError("model_name is required. Use settings.CODE_EXPLORER_MODEL, settings.PLANNER_MODEL, etc.")

    if not settings.INFERENCE_API_ENDPOINT or not settings.INFERENCE_API_TOKEN:
        raise ValueError("INFERENCE_API_ENDPOINT and INFERENCE_API_TOKEN are required")

    logger.info(f"Initializing LLM with model: {model_name}")

    # Create httpx client with configurable SSL verification
    import httpx
    http_client = httpx.Client(verify=settings.VERIFY_SSL)
    async_http_client = httpx.AsyncClient(verify=settings.VERIFY_SSL)

    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        openai_api_key=settings.INFERENCE_API_TOKEN,
        openai_api_base=f"{settings.INFERENCE_API_ENDPOINT}/v1",
        max_tokens=settings.AGENT_MAX_TOKENS,
        http_client=http_client,
        http_async_client=async_http_client
    )
