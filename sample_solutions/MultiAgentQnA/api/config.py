"""
Configuration settings for Multi-Agent Q&A API
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

INFERENCE_API_ENDPOINT = os.getenv("INFERENCE_API_ENDPOINT", "https://api.example.com")
INFERENCE_API_TOKEN = os.getenv("INFERENCE_API_TOKEN")

EMBEDDING_API_ENDPOINT = os.getenv("EMBEDDING_API_ENDPOINT")

if not EMBEDDING_API_ENDPOINT:
    EMBEDDING_API_ENDPOINT = INFERENCE_API_ENDPOINT

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "bge-base-en-v1.5")
INFERENCE_MODEL_NAME = os.getenv("INFERENCE_MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct")

if not INFERENCE_API_TOKEN:
    raise ValueError("INFERENCE_API_TOKEN must be set in environment variables")

# SSL Verification Settings
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() == "true"

# Application Settings
APP_TITLE = "Multi-Agent Q&A"
APP_DESCRIPTION = "A multi-agent Q&A system using CrewAI"
APP_VERSION = "1.0.0"

# CORS Settings
CORS_ALLOW_ORIGINS = ["*"]  # Update with specific origins in production
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

