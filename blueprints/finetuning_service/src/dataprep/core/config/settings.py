import os
from pathlib import Path
from typing import List


class Settings:
    """Application settings and configuration"""
    
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    METADATA_FILE: str = "files_metadata.json"
    
    # API settings
    API_TITLE: str = "Data Preparation Backend for Finetuning"
    API_VERSION: str = "1.0.0"
    HOST: str = os.getenv("HOST")
    PORT: int = int(os.getenv("PORT"))
    # Reverse-proxy prefix stripped by APISIX before reaching this service.
    # Set to /enterprise-ai/dataprep in production so FastAPI passes it as
    # root_path to Starlette — Swagger UI then constructs schema/docs URLs
    # as https://<host>/enterprise-ai/dataprep/openapi.json (which APISIX routes).
    API_BASE_PATH: str = os.getenv("API_BASE_PATH", "")

    # CORS settings - comma-separated list of allowed origins
    # Example: "http://localhost:3000,https://app.example.com"
    # Do NOT use "*" with allow_credentials=True (browsers block it)
    # NOTE: property reads os.environ at call-time so it picks up any runtime
    #       overrides without requiring a process restart in tests.
    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        """Return list of allowed CORS origins from the ALLOWED_ORIGINS env var."""
        raw = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    
    # PostgreSQL settings
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: int = int(os.getenv("DB_PORT"))
    DB_NAME: str = os.getenv("DB_NAME")
    DB_USER: str = os.getenv("DB_USER")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE"))
    
    # MinIO/S3 settings
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY")
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() in ["true", "1", "yes"]
    MINIO_REGION: str = os.getenv("MINIO_REGION")
    MINIO_CERT_VERIFY: bool = os.getenv("MINIO_CERT_VERIFY", "false").lower() in ["true", "1", "yes"]
    
    # Keycloak settings
    KEYCLOAK_ENABLED: bool = os.getenv("KEYCLOAK_ENABLED", "false").lower() in ["true", "1", "yes"]
    KEYCLOAK_URL: str = os.getenv("KEYCLOAK_URL")
    KEYCLOAK_REALM: str = os.getenv("KEYCLOAK_REALM")
    KEYCLOAK_CLIENT_ID: str = os.getenv("KEYCLOAK_CLIENT_ID")
    KEYCLOAK_CLIENT_SECRET: str = os.getenv("KEYCLOAK_CLIENT_SECRET")
    KEYCLOAK_VERIFY_SSL: bool = os.getenv("KEYCLOAK_VERIFY_SSL", "false").lower() in ["true", "1", "yes"]
    
    @property
    def metadata_path(self) -> Path:
        """Get full path to metadata file"""
        return self.BASE_DIR / self.METADATA_FILE
    
    @property
    def keycloak_realm_url(self) -> str:
        """Get full Keycloak realm URL"""
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"
    
    @property
    def keycloak_public_key_url(self) -> str:
        """Get Keycloak public key/certs URL"""
        return f"{self.keycloak_realm_url}/protocol/openid-connect/certs"


settings = Settings()
