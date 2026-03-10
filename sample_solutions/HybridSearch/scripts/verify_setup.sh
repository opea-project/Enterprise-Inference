#!/bin/bash

# Hybrid Search RAG - Setup Verification Script
# This script verifies that the project structure is complete

set -e

echo "======================================"
echo "Hybrid Search RAG - Setup Verification"
echo "======================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if directory exists
check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} Directory exists: $1"
        return 0
    else
        echo -e "${RED}✗${NC} Directory missing: $1"
        return 1
    fi
}

# Function to check if file exists
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} File exists: $1"
        return 0
    else
        echo -e "${RED}✗${NC} File missing: $1"
        return 1
    fi
}

echo "Checking project structure..."
echo ""

# Check main directories
echo "Main Directories:"
check_dir "api"
check_dir "ui"
check_dir "data"
check_dir "tests"
check_dir "scripts"
echo ""

# Check API services
echo "API Services:"
check_dir "api/gateway"
check_dir "api/embedding"
check_dir "api/retrieval"
check_dir "api/llm"
check_dir "api/ingestion"
echo ""

# Check configuration files
echo "Configuration Files:"
check_file "env.example"
check_file "docker-compose.yml"
check_file ".gitignore"
check_file "README.md"
check_file "IMPLEMENTATION_PLAN.md"
check_file "SETUP_SUMMARY.md"
check_file "architecture.md"
echo ""

# Check requirements files
echo "Requirements Files:"
check_file "api/gateway/requirements.txt"
check_file "api/embedding/requirements.txt"
check_file "api/retrieval/requirements.txt"
check_file "api/llm/requirements.txt"
check_file "api/ingestion/requirements.txt"
check_file "ui/requirements.txt"
echo ""

# Check subdirectories
echo "Service Subdirectories:"
check_dir "api/gateway/routers"
check_dir "api/gateway/services"
check_dir "api/retrieval/services"
check_dir "api/llm/models"
check_dir "api/llm/prompts"
check_dir "api/ingestion/services"
check_dir "ui/pages"
check_dir "ui/components"
echo ""

# Check data directories
echo "Data Directories:"
check_dir "data/documents"
check_dir "data/indexes"
check_file "data/documents/.gitkeep"
check_file "data/indexes/.gitkeep"
echo ""

# Check for .env file
echo "Environment Configuration:"
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} .env file exists"
    
    # Check if OpenAI API key is set
    if grep -q "OPENAI_API_KEY=sk-" .env 2>/dev/null; then
        echo -e "${GREEN}✓${NC} OpenAI API key is configured"
    elif grep -q "OPENAI_API_KEY=your-openai-api-key-here" .env 2>/dev/null; then
        echo -e "${YELLOW}!${NC} OpenAI API key needs to be updated"
    else
        echo -e "${YELLOW}!${NC} OpenAI API key not found in .env"
    fi
else
    echo -e "${YELLOW}!${NC} .env file not found (copy from env.example)"
fi
echo ""

# Summary
echo "======================================"
echo "Verification Complete!"
echo "======================================"
echo ""
echo "Next Steps:"
echo "1. Copy env.example to .env: cp env.example .env"
echo "2. Add your OpenAI API key to .env"
echo "3. Review SETUP_SUMMARY.md for implementation roadmap"
echo "4. Start implementing services in this order:"
echo "   a. Embedding Service"
echo "   b. LLM Service"
echo "   c. Document Ingestion Service"
echo "   d. Retrieval Service"
echo "   e. Gateway Service"
echo "   f. UI Service"
echo ""
echo "See SETUP_SUMMARY.md for detailed implementation guide"
echo ""

