"""
Configuration management for DocuGen AI
Supports GenAI Gateway and Keycloak authentication
"""

import os
from enum import Enum
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings with unified inference configuration"""

    # Application Info
    APP_TITLE: str = "DocuGen Micro-Agents"
    APP_DESCRIPTION: str = "AI-powered documentation generation with specialized micro-agent system"
    APP_VERSION: str = "1.0.0"

    # Server Configuration
    API_PORT: int = 5001
    HOST: str = "0.0.0.0"

    # CORS Settings
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"]

    # Inference API Configuration
    # Supports multiple inference deployment patterns:
    #   - GenAI Gateway: Provide your GenAI Gateway URL and API key
    #   - APISIX Gateway: Provide your APISIX Gateway URL and authentication token
    INFERENCE_API_ENDPOINT: Optional[str] = None
    INFERENCE_API_TOKEN: Optional[str] = None

    # Security Configuration
    VERIFY_SSL: bool = True

    # Docker Network Configuration
    LOCAL_URL_ENDPOINT: str = "not-needed"

    # Micro-Agent Model Configuration (Using SLM - Qwen3-4B)
    CODE_EXPLORER_MODEL: str = "Qwen/Qwen3-4B-Instruct-2507"
    API_REFERENCE_MODEL: str = "Qwen/Qwen3-4B-Instruct-2507"
    CALL_GRAPH_MODEL: str = "Qwen/Qwen3-4B-Instruct-2507"
    ERROR_ANALYSIS_MODEL: str = "Qwen/Qwen3-4B-Instruct-2507"
    ENV_CONFIG_MODEL: str = "Qwen/Qwen3-4B-Instruct-2507"
    DEPENDENCY_ANALYZER_MODEL: str = "Qwen/Qwen3-4B-Instruct-2507"
    PLANNER_MODEL: str = "Qwen/Qwen3-4B-Instruct-2507"
    MERMAID_MODEL: str = "Qwen/Qwen3-4B-Instruct-2507"
    QA_VALIDATOR_MODEL: str = "Qwen/Qwen3-4B-Instruct-2507"
    WRITER_MODEL: str = "Qwen/Qwen3-4B-Instruct-2507"


    # Repository Settings
    TEMP_REPO_DIR: str = "./tmp/repos"
    MAX_REPO_SIZE: int = 10737418240  # 10GB in bytes
    MAX_FILE_SIZE: int = 1000000  # 1MB
    MAX_FILES_TO_SCAN: int = 500
    MAX_LINES_PER_FILE: int = 500  # Line budget per file (pattern_window extracts ~150-300 lines)

    # GitHub Integration (for MCP PR creation)
    GITHUB_TOKEN: Optional[str] = None

    # Agent Settings
    AGENT_TEMPERATURE: float = 0.7
    AGENT_MAX_TOKENS: int = 1000
    AGENT_TIMEOUT: int = 300  # 5 minutes

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
