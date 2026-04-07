"""
Document Ingestion Service Configuration
Manages environment variables and service settings
"""

from pydantic_settings import BaseSettings
from pathlib import Path

# Compute project root path (hybrid-search/)
# config.py is at: hybrid-search/api/ingestion/config.py
# So we need to go up 3 levels: ingestion -> api -> hybrid-search
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_DOCUMENT_PATH = str(_PROJECT_ROOT / "data" / "documents")
_DEFAULT_INDEX_PATH = str(_PROJECT_ROOT / "data" / "indexes")
_DEFAULT_DB_PATH = str(_PROJECT_ROOT / "data" / "metadata.db")


class Settings(BaseSettings):
    """
    Service configuration with environment variable loading.

    This class defines configuration for the Ingestion Service, including:
    - Service host and port
    - Downstream service URLs
    - Document storage paths
    - File processing settings (chunk size, overlap, formats)
    - Product catalog settings
    """
    
    # Deployment Phase
    deployment_phase: str = "development"
    
    # Service Configuration
    ingestion_port: int = 8004
    ingestion_host: str = "0.0.0.0"  # nosec B104 - Binding to all interfaces is intentional for Docker container
    
    # Embedding Service
    embedding_service_url: str = "http://localhost:8001"
    
    # Storage Paths (default to local development paths)
    document_storage_path: str = _DEFAULT_DOCUMENT_PATH
    index_storage_path: str = _DEFAULT_INDEX_PATH
    metadata_db_path: str = _DEFAULT_DB_PATH
    
    # Document Processing
    chunk_size: int = 256  # tokens (reduced to safe limit for 512-token models)
    chunk_overlap: int = 25  # tokens
    max_file_size_mb: int = 100
    supported_formats: str = "pdf,docx,xlsx,ppt,txt"
    embedding_dim: int = 768  # BAAI/bge-base-en-v1.5 dimensions
    embedding_batch_size: int = 32  # must match batch size from embedding service
    
    # Product Catalog Settings
    system_mode: str = "document"  # "document" or "product"
    embedding_field_template: str = "{name}. {description}. Category: {category}. Brand: {brand}"
    default_result_limit: int = 20
    max_products_per_catalog: int = 50000
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        # Look for .env file in the hybrid-search root directory
        env_file = Path(__file__).parent.parent.parent / ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file
    
    @property
    def supported_formats_list(self) -> list:
        """Get list of supported formats"""
        return [fmt.strip() for fmt in self.supported_formats.split(",")]


# Global settings instance
settings = Settings()

