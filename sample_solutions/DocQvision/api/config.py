"""
Application configuration management.

Supports GenAI Gateway, APISIX Gateway, and any OpenAI-compatible inference endpoint.
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


# Inference API Configuration
# Supports multiple inference deployment patterns:
#   - GenAI Gateway: Provide your GenAI Gateway URL and API key
#   - APISIX Gateway: Provide your APISIX Gateway URL and authentication token
INFERENCE_API_ENDPOINT: Optional[str] = os.getenv("INFERENCE_API_ENDPOINT")
INFERENCE_API_TOKEN: Optional[str] = os.getenv("INFERENCE_API_TOKEN")

# Security Configuration
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() in ("true", "1", "yes")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./DocQvision.db")

# Application Settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# Vision Model Configuration
VISION_MODEL = os.getenv("VISION_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")
VISION_MAX_TOKENS = int(os.getenv("VISION_MAX_TOKENS", "4000"))
VISION_TEMPERATURE = float(os.getenv("VISION_TEMPERATURE", "0.1"))

# Document Type Detection Model
DETECTION_MODEL = os.getenv("DETECTION_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")

# File Upload Limits
MAX_FILE_SIZE = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "50"))
MAX_BATCH_UPLOAD = int(os.getenv("MAX_BATCH_UPLOAD", "5"))
ALLOWED_EXTENSIONS = {".pdf"}

# Extraction Pipeline Configuration
EXTRACTION_COVERAGE_THRESHOLD = float(os.getenv("EXTRACTION_COVERAGE_THRESHOLD", "0.8"))
VISION_MAX_PAGES = int(os.getenv("VISION_MAX_PAGES", "5"))  # Increased to handle multi-page documents


def validate_auth_config() -> None:
    """
    Validate authentication configuration on startup

    Raises:
        ValueError: If required configuration is missing
    """
    if not INFERENCE_API_ENDPOINT:
        raise ValueError("INFERENCE_API_ENDPOINT is required")
    if not INFERENCE_API_TOKEN:
        raise ValueError("INFERENCE_API_TOKEN is required")
