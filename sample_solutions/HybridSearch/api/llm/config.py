"""
LLM Service Configuration
Manages environment variables and service settings
Supports GenAI Gateway and APISIX Gateway
"""

from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """
    Service configuration with environment variable loading.

    This class defines the configuration settings for the LLM Service,
    including deployment phase and GenAI Gateway/APISIX Gateway settings.
    """

    # Deployment Phase
    deployment_phase: str = "development"

    # GenAI Gateway Configuration
    # Supports multiple deployment patterns:
    #   - GenAI Gateway: Provide GENAI_GATEWAY_URL and GENAI_API_KEY
    #   - APISIX Gateway: Provide GENAI_GATEWAY_URL and GENAI_API_KEY
    genai_gateway_url: Optional[str] = None
    genai_api_key: Optional[str] = None

    # Per-model endpoint URL (required for APISIX, optional for GenAI Gateway)
    llm_api_endpoint: Optional[str] = None

    # Model Configuration (for Enterprise)
    llm_model_endpoint: str = "Qwen/Qwen3-4B-Instruct-2507"
    llm_model_name: str = "Qwen/Qwen3-4B-Instruct-2507"

    # Dual Model Configuration
    inference_model_endpoint_simple: str = "Qwen3-4B-Instruct-2507-vllmcpu"
    inference_model_name_simple: str = "Qwen/Qwen3-4B-Instruct-2507"

    inference_model_endpoint_complex: str = "Qwen3-4B-Instruct-2507-vllmcpu"
    inference_model_name_complex: str = "Qwen/Qwen3-4B-Instruct-2507"

    # Service Configuration
    llm_port: int = 8003
    llm_host: str = "0.0.0.0"  # nosec B104 - Binding to all interfaces is intentional for Docker container

    # LLM Parameters
    max_tokens_simple: int = 512
    max_tokens_complex: int = 512
    temperature_simple: float = 0.1
    temperature_complex: float = 0.6

    # SSL Verification Settings
    verify_ssl: bool = True

    # Product Catalog Settings
    system_mode: str = "document"  # "document" or "product"

    # Logging
    log_level: str = "INFO"

    class Config:
        """Pydantic configuration."""
        # Look for .env file in the hybrid-search root directory
        env_file = Path(__file__).parent.parent.parent / ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file

    def is_enterprise_configured(self) -> bool:
        """
        Check if GenAI Gateway is configured.

        Returns:
            bool: True if genai_gateway_url and genai_api_key are present.
        """
        return bool(self.genai_gateway_url and self.genai_api_key)

    def validate_config(self):
        """
        Validate that GenAI Gateway is configured.

        This service requires GenAI Gateway or APISIX Gateway authentication.

        Raises:
            ValueError: If required configuration is missing.
        """
        if not self.is_enterprise_configured():
            raise ValueError(
                "GenAI Gateway configuration missing. "
                "Must provide GENAI_GATEWAY_URL and GENAI_API_KEY in .env file."
            )


# Global settings instance
settings = Settings()

# Validate configuration on import
settings.validate_config()
