# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
FROM nvidia/cuda:13.1.1-cudnn-devel-ubuntu22.04

# Set working directory
WORKDIR /app

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    git \
    wget \
    curl \
    zip \
    unzip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a dedicated non-root user for running the application (UID/GID 1000).
# Running as root inside a container is a CIS Docker Benchmark violation.
RUN groupadd --gid 1000 appuser \
 && useradd  --uid 1000 --gid 1000 --no-create-home --shell /bin/bash appuser

# Upgrade pip
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ /app/

# Create necessary directories and set ownership BEFORE switching to non-root user
RUN mkdir -p /tmp/finetune_data /tmp/finetune_models /tmp/finetune_logs /app/certs \
 && chown -R appuser:appuser /app /tmp/finetune_data /tmp/finetune_models /tmp/finetune_logs

# Make startup script executable
RUN chmod +x /app/start.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
# Single GPU configuration
ENV CUDA_VISIBLE_DEVICES=0
# Disable TorchDynamo and torch compilation to prevent Triton GPU backend errors
ENV TORCHDYNAMO_DISABLE=1
ENV TORCH_COMPILE_DISABLE=1
# PyTorch memory allocator configuration (MUST be set before CUDA initialization)
ENV PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# Expose ports
EXPOSE 8000 8443

# Switch to non-root user – all subsequent RUN / CMD / ENTRYPOINT instructions
# (and the container process itself) will execute as UID 1000.
USER appuser

# Run the application
CMD ["./start.sh"]