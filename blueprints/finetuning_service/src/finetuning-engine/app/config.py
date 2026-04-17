# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import logging
import os
import torch
from pydantic_settings import BaseSettings
from typing import Optional

logger = logging.getLogger("uvicorn")

class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "GPU Accelerated Fine-tuning Engine"
    ENV: str  # Required: 'development' or 'production'
    LOG_LEVEL: str = "INFO"

    # Keycloak Settings
    KEYCLOAK_ISSUER: str  # Required: e.g. https://keycloak/realms/myrealm
    KEYCLOAK_AUDIENCE: str  # Required: client-id used as audience (azp)
    # Internal URL used for JWKS fetch inside Docker (container-name based).
    # Leave empty to fall back to KEYCLOAK_ISSUER (useful in dev/non-Docker).
    KEYCLOAK_INTERNAL_URL: str = ""  # e.g. https://keycloak:8443/realms/finetuning
    # Set to False only in dev/test environments with self-signed certs.
    KEYCLOAK_TLS_VERIFY: bool = True

    # CORS Settings
    ALLOWED_ORIGINS: str = "http://localhost:3000"  # Comma-separated list of allowed origins

    # Database Settings
    DATABASE_URL: str  # Required: Set by setup script
    
    # File Service Settings
    FILES_API_URL: str  # Required: Set by setup script
    FILES_API_TIMEOUT: int = 14400  # 4 hours for large files
    FILES_API_UPLOAD_TIMEOUT: int = 14400  # 4 hours for large files
    
    # Storage Paths
    TEMP_DATA_DIR: str = "/tmp/finetune_data"
    MODEL_OUTPUT_DIR: str = "/tmp/finetune_models"
    LOG_DIR: str = "/tmp/finetune_logs"
    
    # GPU & Training Settings (Required - set by setup script)
    MAX_CONCURRENT_JOBS: int  # Required
    GPU_MEMORY_THRESHOLD_GB: float  # Required
    DEFAULT_MAX_SEQ_LENGTH: int  # Required
    DEFAULT_BATCH_SIZE: int  # Required
    DEFAULT_GRADIENT_ACCUMULATION: int  # Required
    DEFAULT_LEARNING_RATE: float = 2e-4
    DEFAULT_NUM_EPOCHS: int = 3

    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Ensure directories exist
for directory in [settings.TEMP_DATA_DIR, settings.MODEL_OUTPUT_DIR, settings.LOG_DIR]:
    os.makedirs(directory, exist_ok=True)
    logger.info(f"Ensured directory exists: {directory}")

# GPU Detection and Configuration
def get_gpu_info():
    """Detect GPU availability and configuration"""
    if torch.cuda.is_available():
        gpu_count = torch.cuda.device_count()
        gpu_name = torch.cuda.get_device_name(0)
        total_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        
        logger.info(f"GPU Detection: Found {gpu_count} GPU(s)")
        logger.info(f"GPU Name: {gpu_name}")
        logger.info(f"Total GPU Memory: {total_memory_gb:.2f} GB")
        logger.info(f"CUDA Version: {torch.version.cuda}")
        logger.info(f"BF16 Supported: {torch.cuda.is_bf16_supported()}")
        
        return {
            "available": True,
            "count": gpu_count,
            "name": gpu_name,
            "total_memory_gb": total_memory_gb,
            "cuda_version": torch.version.cuda,
            "bf16_supported": torch.cuda.is_bf16_supported()
        }
    else:
        logger.warning("No GPU detected! This service requires NVIDIA GPU.")
        return {"available": False}

GPU_INFO = get_gpu_info()
