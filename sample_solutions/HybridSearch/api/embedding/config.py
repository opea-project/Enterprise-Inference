"""
Embedding Service Configuration
Manages environment variables and service settings
Supports GenAI Gateway and APISIX Gateway
"""

from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """
    Service configuration with environment variable loading.

    This class defines the configuration settings for the Embedding Service,
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
    
    # Model Configuration (for Enterprise)
    embedding_model_endpoint: str = "bge-large-en-v1.5-vllmcpu"
    embedding_model_name: str = "BAAI/bge-large-en-v1.5"
    
    # Service Configuration
    embedding_port: int = 8001
    embedding_host: str = "0.0.0.0"  # nosec B104 - Binding to all interfaces is intentional for Docker container
    embedding_batch_size: int = 32
    embedding_max_length: int = 512

    # SSL Verification Settings
    verify_ssl: bool = True

    # Logging
    log_level: str = "INFO"
    
    class Config:
        # Look for .env file in the hybrid-search root directory
        env_file = Path(__file__).parent.parent.parent / ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file that aren't defined in this model
    
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
