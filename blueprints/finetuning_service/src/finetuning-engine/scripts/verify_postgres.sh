#!/bin/bash

# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

###############################################################################
# PostgreSQL Verification Script
#
# This script verifies that PostgreSQL is properly set up and accessible.
# It's simpler than setup_postgres.sh and just checks the existing configuration.
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}PostgreSQL Verification${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}✗ .env file not found at: $ENV_FILE${NC}"
    echo ""
    echo "Please create .env file first:"
    echo "  cp .env.example .env"
    exit 1
fi

# Read credentials from .env file
POSTGRES_USER=$(grep "^POSTGRES_USER=" "$ENV_FILE" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
POSTGRES_DB=$(grep "^POSTGRES_DB=" "$ENV_FILE" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
POSTGRES_PASSWORD=$(grep "^POSTGRES_PASSWORD=" "$ENV_FILE" | cut -d '=' -f2- | tr -d '"' | tr -d "'")

if [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_DB" ] || [ -z "$POSTGRES_PASSWORD" ]; then
    echo -e "${RED}✗ Missing POSTGRES_USER, POSTGRES_DB, or POSTGRES_PASSWORD in .env${NC}"
    exit 1
fi

# Check if PostgreSQL container is running
if ! docker compose ps postgres 2>/dev/null | grep -q "Up"; then
    echo -e "${RED}✗ PostgreSQL container is not running${NC}"
    echo ""
    echo "Start it with:"
    echo "  docker compose up -d postgres"
    exit 1
fi
echo -e "${GREEN}✓ PostgreSQL container is running${NC}"

# Get PostgreSQL configuration
echo -e "${YELLOW}Checking PostgreSQL configuration...${NC}"

DB_USER="$POSTGRES_USER"
DB_NAME="$POSTGRES_DB"
DB_PASS="$POSTGRES_PASSWORD"

echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo ""

# Test connection
echo -e "${YELLOW}Testing database connection...${NC}"
if docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Connection successful${NC}"
else
    echo -e "${RED}✗ Connection failed${NC}"
    exit 1
fi
echo ""

# Check if tables exist
echo -e "${YELLOW}Checking for application tables...${NC}"
TABLE_COUNT=$(docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' \r\n')

if [ "$TABLE_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $TABLE_COUNT table(s)${NC}"
    echo -e "${YELLOW}Tables:${NC}"
    docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -c "\dt" 2>/dev/null || echo "  (No tables yet)"
else
    echo -e "${YELLOW}⚠ No tables found (will be created on first app run)${NC}"
fi
echo ""

# Display connection string
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Configuration Summary${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Add this to your .env file:"
echo ""
echo -e "${YELLOW}DATABASE_URL=\"postgresql+asyncpg://$DB_USER:$DB_PASS@postgres:5432/$DB_NAME\"${NC}"
echo ""
echo -e "${YELLOW}Or for connecting from host machine:${NC}"
echo ""
echo -e "${YELLOW}DATABASE_URL=\"postgresql+asyncpg://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME\"${NC}"
echo ""
echo -e "${GREEN}✓ PostgreSQL is ready to use!${NC}"
echo ""
echo "Next steps:"
echo "  1. Ensure DATABASE_URL in .env uses the credentials above"
echo "  2. Start the API: docker compose up -d finetune-api"
echo "  3. Check logs: docker compose logs -f finetune-api"
echo ""
