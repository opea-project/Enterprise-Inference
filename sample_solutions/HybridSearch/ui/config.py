"""
Configuration for UI Service
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Service URLs (use localhost for local dev, gateway for Docker)
    gateway_service_url: str = "http://localhost:8000"
    
    # UI Configuration
    ui_title: str = "InsightMapper Lite"
    ui_page_icon: str = "📚"
    ui_layout: str = "wide"
    
    # Feature flags
    enable_debug_mode: bool = True
    enable_document_upload: bool = True
    enable_query_history: bool = True
    
    # Display settings
    max_results_display: int = 5
    show_confidence_scores: bool = True
    show_source_preview: bool = True
    
    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = Path(__file__).parent.parent / ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()

