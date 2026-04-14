"""
Application Configuration with validation and type safety
Production-grade configuration management using Pydantic Settings
"""

from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum


class Environment(str, Enum):
    """Application environment"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseSettings(BaseSettings):
    """Database configuration with validation"""
    model_config = SettingsConfigDict(env_prefix='DATABASE_', extra='ignore')

    url: str = Field(..., description="PostgreSQL connection URL")
    pool_min_size: int = Field(default=5, ge=1, le=50, description="Minimum pool size")
    pool_max_size: int = Field(default=20, ge=1, le=100, description="Maximum pool size")
    pool_timeout: int = Field(default=30, ge=5, le=300, description="Pool timeout in seconds")
    command_timeout: int = Field(default=60, ge=10, le=600, description="Command timeout in seconds")

    @field_validator('url')
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format"""
        if not v:
            raise ValueError("DATABASE_URL is required")
        if not v.startswith(('postgresql://', 'postgres://')):
            raise ValueError("DATABASE_URL must start with postgresql:// or postgres://")
        return v


class KeycloakSettings(BaseSettings):
    """Keycloak OIDC configuration"""
    model_config = SettingsConfigDict(env_prefix='KEYCLOAK_', extra='ignore')

    issuer: str = Field(..., description="Keycloak issuer URL (realm URL)")
    audience: Optional[str] = Field(default=None, description="Expected audience in JWT")

    @field_validator('issuer')
    @classmethod
    def validate_issuer(cls, v: str) -> str:
        """Validate Keycloak issuer URL"""
        if not v:
            raise ValueError("KEYCLOAK_ISSUER is required")
        if not v.startswith(('http://', 'https://')):
            raise ValueError("KEYCLOAK_ISSUER must be a valid HTTP(S) URL")
        return v.rstrip('/')


class NvidiaBackendSettings(BaseSettings):
    """Nvidia/Unsloth backend configuration"""
    model_config = SettingsConfigDict(env_prefix='NVIDIA_', extra='ignore')

    api_url: str = Field(..., description="Nvidia backend API URL")
    api_timeout: int = Field(default=120, ge=10, le=600, description="API timeout in seconds")
    max_jobs: int = Field(default=1, ge=1, le=10, description="Max concurrent jobs")

    # Keycloak OAuth2 Client Credentials for backend authentication
    keycloak_token_url: str = Field(..., description="Keycloak token endpoint URL")
    keycloak_client_id: str = Field(..., description="OAuth2 client ID")
    keycloak_client_secret: str = Field(..., description="OAuth2 client secret")
    keycloak_verify_ssl: bool = Field(default=True, description="Verify SSL certificates")

    @field_validator('api_url')
    @classmethod
    def validate_api_url(cls, v: str) -> str:
        """Validate API URL format"""
        if not v:
            raise ValueError("NVIDIA_API_URL is required")
        if not v.startswith(('http://', 'https://')):
            raise ValueError("NVIDIA_API_URL must be a valid HTTP(S) URL")
        return v.rstrip('/')

    @field_validator('keycloak_token_url')
    @classmethod
    def validate_token_url(cls, v: str) -> str:
        """Validate Keycloak token URL"""
        if not v:
            raise ValueError("NVIDIA_KEYCLOAK_TOKEN_URL is required")
        if not v.startswith(('http://', 'https://')):
            raise ValueError("NVIDIA_KEYCLOAK_TOKEN_URL must be a valid HTTP(S) URL")
        return v.rstrip('/')


class DataPrepSettings(BaseSettings):
    """Data preparation service configuration"""
    model_config = SettingsConfigDict(env_prefix='DATAPREP_', extra='ignore')

    api_url: Optional[str] = Field(default=None, description="Data prep API URL")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    timeout: int = Field(default=10, ge=5, le=60, description="Request timeout in seconds")

    @field_validator('api_url')
    @classmethod
    def validate_api_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate API URL if provided"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError("DATAPREP_API_URL must be a valid HTTP(S) URL")
        return v.rstrip('/') if v else None


class APISettings(BaseSettings):
    """API-specific settings"""
    model_config = SettingsConfigDict(env_prefix='API_', extra='ignore')

    base_path: str = Field(default="/enterprise-ai", description="API base path for sub-path deployment")
    title: str = Field(default="Production Fine-Tuning Service", description="API title")
    version: str = Field(default="1.0.0", description="API version")
    description: str = Field(
        default="Enterprise-grade API for fine-tuning large language models",
        description="API description"
    )

    # CORS settings - Industry best practices for production security
    cors_origins: List[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins"
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials in CORS")
    cors_allow_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        description="Allowed HTTP methods"
    )
    cors_allow_headers: List[str] = Field(
        default=[
            "Authorization",      # JWT Bearer tokens (Keycloak OIDC)
            "Content-Type",       # Request body type (application/json)
            "Accept",             # Response type negotiation
            "ft-api-key",         # Custom header for nvidia backend
            "X-Requested-With",   # Standard header for AJAX requests
            "Cache-Control",      # Cache directives
            "Pragma",             # HTTP/1.0 cache control
            "Origin",             # CORS origin header
            "User-Agent",         # Client identification
            "Accept-Language",    # Language preferences
            "Accept-Encoding",    # Compression preferences
        ],
        description="Explicitly allowed CORS headers (no wildcards for security)"
    )
    cors_expose_headers: List[str] = Field(
        default=[
            "X-Process-Time",     # Request processing duration
            "X-RateLimit-Limit",  # Rate limit maximum
            "X-RateLimit-Remaining",  # Rate limit remaining
            "X-RateLimit-Reset",  # Rate limit reset time
        ],
        description="Headers exposed to client JavaScript"
    )


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration"""
    model_config = SettingsConfigDict(env_prefix='RATE_LIMIT_', extra='ignore')

    # Global rate limiting toggle
    enabled: bool = Field(default=True, description="Enable rate limiting globally")

    # Default rate limit for all endpoints
    default: int = Field(default=200, ge=1, le=10000, description="Default requests per minute")

    # Health check endpoints (lightweight operations)
    health: int = Field(default=100, ge=1, le=10000, description="Health check requests per minute")

    # Model endpoints (read operations)
    models: int = Field(default=100, ge=1, le=10000, description="Model list/retrieve requests per minute")

    # Job creation (resource-intensive)
    job_create: int = Field(default=10, ge=1, le=1000, description="Job creation requests per minute")

    # Job read operations (listing, retrieve, events)
    job_read: int = Field(default=60, ge=1, le=10000, description="Job read requests per minute")

    # Job cancellation
    job_cancel: int = Field(default=20, ge=1, le=1000, description="Job cancel requests per minute")

    # Job events streaming
    job_events: int = Field(default=60, ge=1, le=10000, description="Job events requests per minute")


class ObservabilitySettings(BaseSettings):
    """Observability and monitoring configuration"""
    model_config = SettingsConfigDict(env_prefix='OBSERVABILITY_', extra='ignore')

    # Global observability toggle
    enabled: bool = Field(default=True, description="Enable observability features (metrics, structured logging)")

    # Structured logging
    json_logs: bool = Field(default=True, description="Use JSON structured logging (recommended for production)")
    log_user_actions: bool = Field(default=True, description="Log user actions in metrics")

    # Prometheus metrics
    metrics_enabled: bool = Field(default=True, description="Enable Prometheus metrics endpoint")
    track_user_metrics: bool = Field(default=True, description="Track per-user request metrics")

    # System metrics
    collect_system_metrics: bool = Field(default=True, description="Collect CPU/memory metrics")


class Settings(BaseSettings):
    """Main application settings"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=False
    )

    environment: Environment = Field(default=Environment.DEVELOPMENT, description="Application environment")
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    debug: bool = Field(default=False, description="Debug mode")

    # Security settings
    max_concurrent_jobs_per_user: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum concurrent active jobs per user (Resource consumption control)"
    )

    # Sub-configurations
    database: DatabaseSettings
    keycloak: KeycloakSettings
    nvidia: NvidiaBackendSettings
    dataprep: DataPrepSettings
    api: APISettings
    rate_limit: RateLimitSettings
    observability: ObservabilitySettings

    def __init__(self, **kwargs):
        # Initialize sub-configurations
        if 'database' not in kwargs:
            kwargs['database'] = DatabaseSettings()
        if 'keycloak' not in kwargs:
            kwargs['keycloak'] = KeycloakSettings()
        if 'nvidia' not in kwargs:
            kwargs['nvidia'] = NvidiaBackendSettings()
        if 'dataprep' not in kwargs:
            kwargs['dataprep'] = DataPrepSettings()
        if 'api' not in kwargs:
            kwargs['api'] = APISettings()
        if 'rate_limit' not in kwargs:
            kwargs['rate_limit'] = RateLimitSettings()
        if 'observability' not in kwargs:
            kwargs['observability'] = ObservabilitySettings()

        super().__init__(**kwargs)

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == Environment.DEVELOPMENT


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get application settings singleton

    This function ensures settings are loaded only once and reused across the application.
    """
    global _settings
    if _settings is None:
        try:
            _settings = Settings()
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}") from e
    return _settings


def reload_settings() -> Settings:
    """Force reload settings (useful for testing)"""
    global _settings
    _settings = None
    return get_settings()
