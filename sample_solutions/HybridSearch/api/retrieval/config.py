"""
Retrieval Service Configuration
Manages environment variables and service settings
"""

from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path

# Compute project root path
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_INDEX_PATH = str(_PROJECT_ROOT / "data" / "indexes")


class Settings(BaseSettings):
    """
    Service configuration with environment variable loading.

    Manages:
    - Service networking (host/port)
    - Embedding service connection
    - GenAI Gateway/APISIX Gateway credentials
    - Model endpoints (Reranker)
    - File paths for Dense (FAISS) and Sparse (BM25) indexes
    - Retrieval parameters (top-k, fusion K)
    """
    
    # Deployment Phase
    deployment_phase: str = "development"
    
    # Service Configuration
    retrieval_port: int = 8002
    retrieval_host: str = "0.0.0.0"  # nosec B104 - Binding to all interfaces is intentional for Docker container
    
    # Embedding Service
    embedding_service_url: str = "http://localhost:8001"

    # GenAI Gateway Configuration
    # Supports multiple deployment patterns:
    #   - GenAI Gateway: Provide GENAI_GATEWAY_URL and GENAI_API_KEY
    #   - APISIX Gateway: Provide GENAI_GATEWAY_URL and GENAI_API_KEY
    genai_gateway_url: Optional[str] = None
    genai_api_key: Optional[str] = None

    # Per-model endpoint URL (required for APISIX, optional for GenAI Gateway)
    reranker_api_endpoint: Optional[str] = None
    
    # Reranker Model Configuration (for Enterprise)
    reranker_model_endpoint: str = "bge-reranker-base-vllmcpu"
    reranker_model_name: str = "BAAI/bge-reranker-base"
    
    # Index Storage Path - default to /data/indexes in Docker
    index_storage_path: str = "/data/indexes"
    
    # Individual Index Paths - can be overridden by environment variables
    faiss_index_path: str = "/data/indexes/faiss_index.bin"
    bm25_index_path: str = "/data/indexes/bm25_index.pkl"
    metadata_index_path: str = "/data/indexes/metadata.pkl"
    
    # Product Index Paths
    product_faiss_index_path: str = "/data/indexes/product_faiss_index.bin"
    product_bm25_index_path: str = "/data/indexes/product_bm25_index.pkl"
    product_metadata_index_path: str = "/data/indexes/product_metadata.pkl"
    
    # Retrieval Configuration
    top_k_dense: int = 100
    top_k_sparse: int = 100
    top_k_fusion: int = 50
    top_k_rerank: int = 10
    use_reranking: bool = False  # Skip in dev phase
    rrf_k: int = 60  # RRF constant
    
    # Product Catalog Settings
    system_mode: str = "document"  # "document" or "product"
    default_result_limit: int = 20
    
    # SSL Verification Settings
    verify_ssl: bool = True

    # Logging
    log_level: str = "INFO"

    class Config:
        # Look for .env file in the hybrid-search root directory
        env_file = Path(__file__).parent.parent.parent / ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file

    def model_post_init(self, __context: any) -> None:
        if not self.is_enterprise_configured():
            if self.use_reranking:
                # If reranking is enabled, we strictly need GenAI Gateway auth
                raise ValueError(
                    "GenAI Gateway configuration missing for RERANKING. "
                    "Must provide GENAI_GATEWAY_URL and GENAI_API_KEY in .env file, "
                    "OR set USE_RERANKING=false."
                )

    def is_enterprise_configured(self) -> bool:
        """
        Check if GenAI Gateway is configured.

        Returns:
            bool: True if genai_gateway_url and genai_api_key are present.
        """
        return bool(self.genai_gateway_url and self.genai_api_key)


# Global settings instance
settings = Settings()
