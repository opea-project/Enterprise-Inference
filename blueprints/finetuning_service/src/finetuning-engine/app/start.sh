#!/bin/bash
# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
# Startup script for Fine-tuning Engine
# Checks ENV variable to determine HTTP (development) or HTTPS (production)

set -e

# Read environment mode (defaults to development if not set)
ENV_MODE="${ENV:-development}"

echo "=========================================="
echo "Fine-tune Engine Startup"
echo "=========================================="
echo "Environment: $ENV_MODE"
echo ""

if [ "$ENV_MODE" = "production" ]; then
    echo "Production Mode - HTTPS Only"

    # Check for SSL certificates
    if [ ! -f "/app/certs/cacert.pem" ] || [ ! -f "/app/certs/private.key" ]; then
        echo "ERROR: Production mode requires SSL certificates!"
        echo ""
        echo "Please ensure the following files exist:"
        echo "   /app/certs/cacert.pem"
        echo "   /app/certs/private.key"
        echo ""
        echo "Mount certificates using docker-compose volumes:"
        echo "   volumes:"
        echo "     - ./certs:/app/certs:ro"
        exit 1
    fi

    echo "SSL certificates found"
    echo "Starting HTTPS on port 8443..."
    echo ""

    # Start HTTPS only
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8443 \
        --ssl-keyfile=/app/certs/private.key \
        --ssl-certfile=/app/certs/cacert.pem \
        --log-level info

else
    echo "Development Mode - HTTP Only"
    echo "Starting HTTP on port 8000..."
    echo ""

    # Start HTTP only
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --log-level info
fi
