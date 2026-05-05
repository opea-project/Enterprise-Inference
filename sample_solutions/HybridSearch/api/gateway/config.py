"""
Gateway Service Configuration
Manages environment variables and service settings
"""

from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """
    Service configuration with environment variable loading.

    This class defines configuration for the Gateway Service, including:
    - Service host and port
    - URLs for downstream services (embedding, retrieval, llm, ingestion)
    - Product catalog specific settings
    - Logging configuration
    """

    # Deployment Phase
    deployment_phase: str = "development"

    # Service Configuration
    gateway_port: int = 8000
    gateway_host: str = "0.0.0.0"  # nosec B104 - Binding to all interfaces is intentional for Docker container

    # Service URLs
    embedding_service_url: str = "http://localhost:8001"
    retrieval_service_url: str = "http://localhost:8002"
    llm_service_url: str = "http://localhost:8003"
    ingestion_service_url: str = "http://localhost:8004"
    
    # Product Catalog Settings
    system_mode: str = "document"  # "document" or "product"
    default_result_limit: int = 20
    
    # Keycloak/Auth Configuration (optional)
    base_url: Optional[str] = None
    keycloak_realm: Optional[str] = None

    # SSL Verification Settings
    verify_ssl: bool = True

    # Logging
    log_level: str = "INFO"
    
    class Config:
        # Look for .env file in the hybrid-search root directory
        env_file = Path(__file__).parent.parent.parent / ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file


# Global settings instance
settings = Settings()

