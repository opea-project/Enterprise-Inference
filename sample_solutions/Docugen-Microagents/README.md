## Documentation Generator

AI-powered documentation generator that automatically creates comprehensive README files from code repositories. This application uses a micro-agent system with nine specialized agents orchestrated by LangGraph to analyze code, extract API endpoints, map call graphs, identify error patterns, parse configurations, and generate documentation with architecture diagrams.

## Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tool System](#tool-system)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [User Interface](#user-interface)
- [Troubleshooting](#troubleshooting)
- [Additional Info](#additional-info)

---

## Project Overview

Documentation Generator is an autonomous system that transforms code repositories into professional README documentation using a specialized micro-agent architecture. The application employs nine specialized AI agents built on LangChain and orchestrated by LangGraph. Six section-writer agents analyze specific aspects of the codebase (project overview, API endpoints, architecture patterns, error handling, environment configuration, and dependencies), while three coordination agents handle planning, diagram generation, and quality validation. The system clones repositories, performs intelligent analysis with strategic file sampling, and generates structured documentation including project descriptions, installation instructions, usage guides, and Mermaid architecture diagrams. Each agent operates with a limited tool set and context budget optimized for efficiency. The system supports both single-project repositories and monorepos with intelligent project detection and user selection capabilities.

---

## Features

- Micro-agent system with nine specialized AI agents optimized for small language models: Code Explorer, API Reference, Call Graph, Error Analysis, Environment Config, Dependency Analyzer, Planner, Mermaid Generator, and QA Validator
- 11 custom repository analysis tools built with LangChain distributed across agents for autonomous code exploration, API extraction, and syntax validation
- Strategic file sampling with three reading strategies: full, smart, and pattern_window (context-aware extraction around routes, errors, and entry points)
- Autonomous repository analysis using ReAct pattern (Thought → Action → Observation) for transparent decision-making
- Intelligent monorepo detection with automatic project discovery and user selection interface
- Subfolder-specific documentation generation via URL targeting (e.g., `https://github.com/owner/repo/tree/main/backend`)
- Support for GitHub public and private repositories with token-based authentication
- Automated pull request creation using Model Context Protocol (MCP) with official GitHub MCP server integration
- Real-time progress tracking via Server-Sent Events (SSE) for live agent activity monitoring
- Mermaid 8.14.0 compatible diagram generation with semantic validation and render-safe checks
- Built on LangChain framework for tool infrastructure and LangGraph for multi-agent workflow orchestration with state persistence
- Evidence-based documentation generation with filesystem verification and agent output aggregation
- Comprehensive metrics tracking including token usage, tool calls, LLM calls, TPS (tokens per second), and execution duration
- Modern React web interface with job history, status monitoring, and documentation preview
- Flexible LLM backend supporting Qwen/Qwen3-4B-Instruct-2507 optimized for Intel Xeon processors
- RESTful API with JSON-based communication for integration capabilities
- Configurable analysis limits via .env (10GB max repo size, 500 files max, 1MB per file, adjustable line budget)

---

## Architecture

This application uses a micro-agent architecture with nine specialized AI agents built on LangChain and orchestrated by LangGraph. The React frontend communicates with a FastAPI backend that orchestrates the workflow. Nine agents operate sequentially within a LangGraph StateGraph workflow: six section-writer agents (Code Explorer, API Reference, Call Graph, Error Analysis, Environment Config, Dependency Analyzer) analyze specific aspects of the codebase and write documentation sections directly, followed by three coordination agents (Planner decides which sections to include, Mermaid Generator creates architecture diagrams with semantic validation, and QA Validator performs evidence-based quality checks). An Evidence Aggregator node consolidates filesystem data and agent outputs before planning. All agents use strategic file sampling with pattern_window mode to extract high-value code regions (routes, error handlers, entry points) within limited context budgets. The system tracks comprehensive metrics including token usage, tool calls, and execution duration. Each agent operates with 3-8 specialized tools and implements the ReAct pattern for autonomous decision-making.

```mermaid
graph TB
    subgraph "Client Layer"
        A[React Web UI<br/>Port 3000]
    end

    subgraph "API Layer"
        B[FastAPI Server<br/>Port 5001<br/>REST API + SSE]
    end

    subgraph "Section Writer Agents"
        C[Code Explorer<br/>Overview + Features]
        D[API Reference<br/>Endpoint Extractor]
        E[Call Graph<br/>Architecture Writer]
        F[Error Analysis<br/>Troubleshooting Writer]
        G[Env Config<br/>Configuration Writer]
        H[Dependency Analyzer<br/>Prerequisites Writer]
    end

    subgraph "Coordination Agents"
        I[Planner<br/>Section Selector]
        J[Mermaid Generator<br/>Diagram + Validation]
        K[QA Validator<br/>Evidence Checks]
    end

    subgraph "GitHub Integration"
        L[PR Agent<br/>MCP Tools]
        M[GitHub MCP Server<br/>Docker Container]
    end

    subgraph "External Services"
        N[LLM Backend<br/>Qwen3-4B-Instruct]
    end

    A -->|POST /generate-docs| B
    A -->|SSE /logs| B
    B -->|Clone & Detect| C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H -->|Evidence Aggregation| I
    I --> J
    J --> K
    K -->|Assembly| B
    B -->|JSON Response| A
    A -->|POST /create-pr| B
    B --> L
    L --> M
    M -->|Branch, Commit, PR| GitHub
    C --> N
    D --> N
    E --> N
    F --> N
    G --> N
    H --> N
    I --> N
    J --> N
    K --> N
    L --> N

    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#ffe1f5
    style D fill:#ffe1f5
    style E fill:#ffe1f5
    style F fill:#ffe1f5
    style G fill:#ffe1f5
    style H fill:#ffe1f5
    style I fill:#d4f1d4
    style J fill:#d4f1d4
    style K fill:#d4f1d4
    style L fill:#ffd4d4
    style M fill:#e1ffe1
    style N fill:#ffe1e1
```

**Strategic File Sampling:**

The system implements three intelligent file reading strategies to optimize context usage with small language models. All strategies work within a configurable line budget (default: 500 lines, set via MAX_LINES_PER_FILE):

- **full** - Reads first N lines within budget. Simple and deterministic for small files.
- **smart** - Extracts top + function/class signatures + bottom sections. Preserves file structure overview while staying within line budget.
- **pattern_window** - Context-aware extraction that detects high-value code patterns (FastAPI/Flask routes, error handlers, entry points, main functions) and extracts ±6 lines around matches. Falls back to smart strategy if no patterns found. This is the default mode for all agents, enabling efficient analysis of large codebases.

All agents use `pattern_window` by default to maximize information density within the 8K context budget optimized for Qwen3-4B. The line budget is configurable via `.env` file to balance context usage and file coverage.

**Core Components:**

1. **React Web UI (Port 3000)** - Vite development server hosting the React frontend. Handles repository URL input with subfolder support, displays real-time generation progress via SSE streaming, provides project selection interface for monorepos, and offers documentation preview with download functionality.

2. **FastAPI Server (Port 5001)** - Manages LangGraph workflow orchestration with state persistence, maintains job state in memory, handles repository cloning with branch detection, performs monorepo project detection, tracks comprehensive metrics (tokens, tool calls, TPS, duration), and coordinates GitHub PR creation via MCP protocol.

3. **Code Explorer Agent** - Writes Project Overview and Features sections. Uses 5 tools: `list_directory`, `read_file`, `detect_languages`, `extract_dependencies`, `analyze_code_structure`. Extracts concrete technical details including project purpose, user-facing capabilities, dependencies, and architecture patterns.

4. **API Reference Agent** - Extracts API endpoints and returns structured JSON. Uses 3 tools: `list_directory`, `read_file`, `find_api_routes`. Identifies REST API routes, HTTP methods, and endpoint purposes from FastAPI, Flask, Express, and Spring frameworks.

5. **Call Graph Agent** - Writes Architecture section describing component relationships and data flow. Uses 5 tools including `find_entry_points` to identify main application files and `analyze_code_structure` to map dependencies.

6. **Error Analysis Agent** - Writes Troubleshooting section by identifying error patterns, exception handlers, and common failure modes. Uses `read_file` with pattern_window to extract try-except blocks and error handling logic.

7. **Environment Config Agent** - Writes Configuration section by analyzing .env.example files and configuration modules. Extracts environment variables, API keys, and deployment settings with their purposes.

8. **Dependency Analyzer Agent** - Writes Prerequisites and Quick Start Deployment sections. Analyzes requirements.txt, package.json, Dockerfile, and docker-compose.yml to generate installation instructions and deployment guides.

9. **Planner Agent** - Determines which sections to include in the final README based on project type (web app, API service, library, CLI tool). Uses 8 tools including `find_ui_files`, `find_docker_files`, `find_config_files` for project detection.

10. **Mermaid Generator Agent** - Creates architecture diagrams with semantic validation. Validates diagrams against evidence packet to ensure accuracy (no endpoint nodes, includes backend/frontend/database based on detected components). Uses `validate_mermaid_syntax` for Mermaid 8.14.0 render-safe checks.

11. **QA Validator Agent** - Performs evidence-based quality validation comparing README sections against filesystem evidence. Checks for hallucinations, missing sections, and factual accuracy before final assembly.

12. **PR Agent** - Autonomous AI agent activated via `/api/create-pr/{job_id}` endpoint after documentation generation. Uses GitHub MCP server tools via Model Context Protocol stdio interface. Executes four-step workflow: checks existing README.md, creates feature branch, commits documentation with conventional commit message, creates pull request with descriptive body.

---

## Tool System

The system includes 11 specialized repository analysis tools implemented in `api/tools/repo_tools.py` using LangChain's `@tool` decorator. These tools enable the nine LangGraph agents to autonomously analyze repositories. Each agent receives a curated subset of tools based on its specific responsibilities. The PR Agent uses a separate set of GitHub tools provided by the GitHub MCP server. All tools are invoked by agents using the ReAct pattern - agents autonomously decide when to call tools, interpret results, and act on observations.

### Tool Distribution Across Agents

| Agent                    | Tool Count | Tools Available                                       |
|--------------------------|------------|-------------------------------------------------------|
| **Code Explorer**        | 5          | Core analysis tools for repository exploration        |
| **API Reference**        | 3          | Directory listing, file reading, API route detection  |
| **Call Graph**           | 5          | Core analysis tools + entry point detection           |
| **Error Analysis**       | 3          | File reading, directory listing, code structure       |
| **Env Config**           | 3          | File reading, config file detection, directory listing|
| **Dependency Analyzer**  | 5          | Core analysis tools + dependency extraction           |
| **Planner**              | 8          | Core tools + project detection tools                  |
| **Mermaid Generator**    | 7          | Selective tools + validation tools                    |
| **QA Validator**         | 0          | No tools (operates on README sections + evidence)     |
| **PR Agent**             | 4          | GitHub MCP tools (via Model Context Protocol)         |

### Core Analysis Tools (5 tools)

**Framework: LangChain (@tool decorator)**
**Used by: Code Explorer, Call Graph, Dependency Analyzer**

1. **`list_directory`** - Browses directory structure with automatic filtering of common ignore patterns (.git, node_modules, __pycache__, venv, dist, build)
2. **`read_file`** - Reads source code and configuration files with strategic sampling (supports full, smart, pattern_window modes). Default: pattern_window for context-aware extraction. Limits: 1MB max file size, configurable line budget (default 500 via MAX_LINES_PER_FILE).
3. **`detect_languages`** - Identifies programming languages by file extensions (supports 16 languages including Python, JavaScript, TypeScript, Go, Rust, Java, C++)
4. **`extract_dependencies`** - Recursively scans subdirectories and parses dependency files (requirements.txt, package.json, go.mod, Cargo.toml). Returns first 20 dependencies per ecosystem.
5. **`analyze_code_structure`** - Extracts functions, classes, and imports using AST parsing (Python) or basic line count metrics (other languages)

### Project Detection Tools (3 tools)

**Framework: LangChain (@tool decorator)**
**Used by: Planner (in addition to core tools)**

6. **`find_ui_files`** - Detects frontend components and frameworks (React, Vue.js, Angular, Next.js, Svelte)
7. **`find_docker_files`** - Checks for Docker and containerization configuration files
8. **`find_config_files`** - Locates environment and configuration files in repository root

### Diagram Generation Tools (2 tools)

**Framework: LangChain (@tool decorator)**
**Used by: Diagram Generator (in addition to selective core tools)**

9. **`find_entry_points`** - Locates main entry point files (main.py, server.py, index.js, etc.) across languages
10. **`find_api_routes`** - Extracts API routes/endpoints using regex for Flask, FastAPI, Express, Spring frameworks

### Validation Tool (1 tool)

**Framework: LangChain (@tool decorator)**
**Used by: Diagram Generator for self-critique**

11. **`validate_mermaid_syntax`** - Validates Mermaid 8.14.0 syntax with automatic error detection and repair suggestions

### GitHub MCP Tools (4 tools)

**Framework: Model Context Protocol (MCP)**
**Used by: PR Agent**

1. **`get_file_contents`** - Retrieves file content and SHA from GitHub repository
2. **`create_branch`** - Creates new feature branch with timestamp-based naming
3. **`create_or_update_file`** - Commits README.md to branch with conventional commit message
4. **`create_pull_request`** - Opens PR with AI-generated title, description, and labels

---

## Prerequisites

### System Requirements

Before you begin, ensure you have the following installed:

- **Docker and Docker Compose**
- **Enterprise inference endpoint access** (token-based authentication)

### Required API Configuration

**For Inference Service (Documentation Generation):**

This application supports multiple inference deployment patterns:

**GenAI Gateway**: Provide your GenAI Gateway URL and API key
- **URL format**: `https://api.example.com`
- To generate the GenAI Gateway API key, use the [generate-vault-secrets.sh](https://github.com/opea-project/Enterprise-Inference/blob/main/core/scripts/generate-vault-secrets.sh) script
- The API key is the `litellm_master_key` value from the generated `vault.yml` file

**APISIX Gateway**: Provide your APISIX Gateway URL and authentication token
- **URL format**: `https://api.example.com/Qwen3-4B-Instruct`
- **Note**: APISIX requires the model name in the URL path (without company/family prefixes)
- To generate the APISIX authentication token, use the [generate-token.sh](https://github.com/opea-project/Enterprise-Inference/blob/main/core/scripts/generate-token.sh) script
- The token is generated using Keycloak client credentials

**Configuration requirements:**
- **INFERENCE_API_ENDPOINT**: URL to your inference service (example: `https://api.example.com`)
- **INFERENCE_API_TOKEN**: Authentication token/API key for your chosen service

**Note:** All nine AI agents (Code Explorer, API Reference, Call Graph, Error Analysis, Env Config, Dependency Analyzer, Planner, Mermaid Generator, QA Validator) plus PR Agent use Qwen/Qwen3-4B-Instruct-2507 optimized for Intel Xeon processors

### Local Development Configuration

**For Local Testing Only (Optional)**

If you're testing with a local inference endpoint using a custom domain (e.g., `api.example.com` mapped to localhost in your hosts file):

1. Edit `api/.env` and set:
   ```bash
   LOCAL_URL_ENDPOINT=api.example.com
   ```
   (Use the domain name from your INFERENCE_API_ENDPOINT without `https://`)

2. This allows Docker containers to resolve your local domain correctly.

**Note:** For public domains or cloud-hosted endpoints, leave the default value `not-needed`.

### GitHub Personal Access Token (Optional)

**For Automatic Pull Request Creation:**

- Required only for PR Agent to create pull requests automatically
- Generate classic token at https://github.com/settings/tokens
- Required scopes: `repo` (full control of private repositories)
- Token format: `ghp_` followed by 36 alphanumeric characters

### Verify Docker Installation

```bash
# Check Docker version
docker --version

# Check Docker Compose version
docker compose version

# Verify Docker is running
docker ps
```

---

## Quick Start Deployment

### Clone the Repository

```bash
git clone https://github.com/cld2labs/GenAISamples.git
cd GenAISamples/Docugen-Microagents
```

### Set up the Environment

This application requires **two `.env` files** for proper configuration:

1. **Root `.env` file** (for Docker Compose variables)
2. **`api/.env` file** (for backend application configuration)

#### Step 1: Create Root `.env` File

```bash
# From the Docugen-Microagents directory
cat > .env << EOF
# Docker Compose Configuration
LOCAL_URL_ENDPOINT=not-needed
EOF
```

**Note:** If using a local domain (e.g., `api.example.com` mapped to localhost), replace `not-needed` with your domain name (without `https://`).

#### Step 2: Create `api/.env` File

Copy from the example file and edit with your actual credentials:

```bash
cp api/.env.example api/.env
```

Then edit `api/.env` to set your `INFERENCE_API_ENDPOINT` and `INFERENCE_API_TOKEN`.

Or manually create `api/.env` with:

```bash
# ==========================================
# Inference API Configuration
# ==========================================
# INFERENCE_API_ENDPOINT: URL to your inference service (without /v1 suffix)
#
# **GenAI Gateway**: Provide your GenAI Gateway URL and API key
#   - URL format: https://genai-gateway.example.com
#   - To generate the GenAI Gateway API key, use the [generate-vault-secrets.sh] script
#   - The API key is the litellm_master_key value from the generated vault.yml file
#
# **APISIX Gateway**: Provide your APISIX Gateway URL and authentication token
#   - For APISIX, include the model name in the INFERENCE_API_ENDPOINT path
#   - Example: https://apisix-gateway.example.com/Qwen3-4B-Instruct
#   - To generate the APISIX authentication token, use the [generate-token.sh] script
#   - The token is generated using Keycloak client credentials
#
# INFERENCE_API_TOKEN: Authentication token/API key for the inference service
INFERENCE_API_ENDPOINT=https://api.example.com
INFERENCE_API_TOKEN=your-pre-generated-token-here

# APISIX Gateway Example (uncomment and configure when using APISIX):
# INFERENCE_API_ENDPOINT=https://api.example.com/Qwen3-4B-Instruct
# INFERENCE_API_TOKEN=your-keycloak-generated-token-here

# ==========================================
# Docker Network Configuration
# ==========================================
# LOCAL_URL_ENDPOINT: Required if using local domain mapping (e.g., api.example.com -> localhost)
# Set to your domain name (without https://) or leave as "not-needed" if using public URLs
LOCAL_URL_ENDPOINT=not-needed

# ==========================================
# Micro-Agent Model Configuration
# ==========================================
# All agents use Qwen3-4B-Instruct (optimized SLM for code analysis)
# You can customize individual agent models if needed

CODE_EXPLORER_MODEL=Qwen/Qwen3-4B-Instruct-2507
API_REFERENCE_MODEL=Qwen/Qwen3-4B-Instruct-2507
CALL_GRAPH_MODEL=Qwen/Qwen3-4B-Instruct-2507
ERROR_ANALYSIS_MODEL=Qwen/Qwen3-4B-Instruct-2507
ENV_CONFIG_MODEL=Qwen/Qwen3-4B-Instruct-2507
DEPENDENCY_ANALYZER_MODEL=Qwen/Qwen3-4B-Instruct-2507
PLANNER_MODEL=Qwen/Qwen3-4B-Instruct-2507
MERMAID_MODEL=Qwen/Qwen3-4B-Instruct-2507
QA_VALIDATOR_MODEL=Qwen/Qwen3-4B-Instruct-2507
WRITER_MODEL=Qwen/Qwen3-4B-Instruct-2507

# ==========================================
# Repository Analysis Limits
# ==========================================
# All limits are configurable to suit your needs
TEMP_REPO_DIR=./tmp/repos
MAX_REPO_SIZE=10737418240    # 10GB in bytes
MAX_FILE_SIZE=1000000         # 1MB in bytes
MAX_FILES_TO_SCAN=500         # Maximum number of files to analyze
MAX_LINES_PER_FILE=500        # Line budget per file (pattern_window strategy extracts ~150-300 lines focusing on key patterns)

# ==========================================
# Agent Execution Settings
# ==========================================
AGENT_TEMPERATURE=0.7         # Model temperature (0.0-1.0)
AGENT_MAX_TOKENS=1000         # Maximum tokens per agent response
AGENT_TIMEOUT=300             # Agent timeout in seconds (5 minutes)

# ==========================================
# GitHub Integration (MCP)
# ==========================================
# Required for automatic PR creation
# Generate token at: https://github.com/settings/tokens
# Required scopes: repo (full access to repositories)
GITHUB_TOKEN=your_github_personal_access_token_here

# ==========================================
# Server Configuration
# ==========================================
API_PORT=5001
HOST=0.0.0.0

# ==========================================
# CORS Settings
# ==========================================
# Add your frontend URL if different from defaults
CORS_ORIGINS=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"]

# ==========================================
# Security Configuration
# ==========================================
# SSL Verification: Set to false only for development with self-signed certificates
VERIFY_SSL=true
```

**Important Configuration Notes:**

- **INFERENCE_API_ENDPOINT**: Your actual inference service URL (replace `https://api.example.com`)
  - For APISIX/Keycloak deployments, the model name must be included in the endpoint URL (e.g., `https://api.example.com/Qwen3-4B-Instruct`)
- **INFERENCE_API_TOKEN**: Your actual pre-generated authentication token
- **Model Names**: Use the exact model names from your inference service
- **LOCAL_URL_ENDPOINT**: Only needed if using local domain mapping

**Note**: The docker-compose.yml file automatically loads environment variables from both `.env` (root) and `./api/.env` (backend) files.

### Running the Application

Start both API and UI services together with Docker Compose:

```bash
# From the Docugen-Microagents directory
docker compose up --build

# Or run in detached mode (background)
docker compose up -d --build
```

What happens during deployment:
- Docker builds images for frontend and backend (first time: 3-5 minutes)
- Creates containers for both services
- Sets up networking between services
- Initializes the workflow engine

### Verify Deployment

Check that all containers are running:

```bash
docker compose ps
```

Expected output - You should see 2 containers with status "Up":

| Container Name | Port | Status |
|----------------|------|--------|
| `Docugen-Microagents-backend` | 5001 | Up (healthy) |
| `Docugen-Microagents-frontend` | 3000 | Up (healthy) |

If any container shows "Restarting" or "Exited", check logs:

```bash
docker compose logs -f
```

**View logs:**

```bash
# All services
docker compose logs -f

# Backend only
docker compose logs -f Docugen-Microagents-backend

# Frontend only
docker compose logs -f Docugen-Microagents-frontend
```

**Verify the services are running:**

```bash
# Check API health endpoint
curl http://localhost:5001/health

# Or open in your browser
# http://localhost:5001/health

# Check if containers are running
docker compose ps
```

### Access the Application

Open your browser and navigate to:

```
http://localhost:3000
```

---

## User Interface

### Homepage
Enter any GitHub repository URL to start documentation generation. Supports full repositories, specific branches, and subfolder paths for monorepos.

![Homepage](./docs/images/01-homepage-input.png)

### Agent Workflow
Watch the nine AI agents work sequentially in real-time. Each agent displays its reasoning process using the ReAct pattern (Thought → Action → Observation). Progress through six section-writer agents, followed by planning, diagram generation, and quality validation.

![Agent Workflow](./docs/images/02-agent-workflow.png)

### Progress Tracking
Monitor live progress with detailed logs from each agent. Server-Sent Events (SSE) provide real-time updates on tool executions, decisions, and analysis results.

![Progress Tracking](./docs/images/03-progress-tracking.png)

### Generated Documentation
Review the complete README with architecture diagrams, installation instructions, and usage guides. Download or create a pull request directly from the interface.

![Generated README](./docs/images/04-generated-readme.png)

### PR Agent Execution
Activate the PR Agent to autonomously create a GitHub pull request. Watch as it checks for existing files, creates a branch, commits changes, and opens a PR with AI-generated descriptions.

![PR Agent Logs](./docs/images/05-pr-agent-execution.png)

### Pull Request Created
PR Agent successfully creates the pull request with conventional commit messages and links it back to the UI for immediate access.

![PR Created](./docs/images/06-pr-created.png)

---

## Troubleshooting

For detailed troubleshooting guidance and solutions to common issues, refer to:

[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

---

## Additional Info

### Model Compatibility

| Model Name | Deployment Platform | Notes |
|------------|---------------------|-------|
| Qwen/Qwen3-4B-Instruct-2507 | Xeon | Optimized SLM with 8K context window for efficient documentation generation across all nine micro-agents. |

### Performance Metrics

The system tracks comprehensive performance metrics for each agent execution, providing visibility into token usage, processing speed, and resource consumption. Metrics are calculated and displayed in real-time during workflow execution:

**Metrics Tracked:**
- **Token Usage** - Input and output tokens per agent, aggregated for total workflow cost
- **Tokens Per Second (TPS)** - Model generation speed measured at two levels:
  - **Per-Agent TPS**: `output_tokens / agent_duration_seconds` - True model inference speed for each agent
  - **Workflow Average TPS**: `total_output_tokens / workflow_duration_seconds` - Overall throughput including inter-agent overhead (typically lower due to I/O and state management gaps)
- **Execution Duration** - Wall-clock time for each agent and total workflow duration
- **LLM Calls** - Number of model inference requests per agent
- **Tool Calls** - Number of repository analysis tool invocations per agent

**TPS Interpretation**: Per-Agent TPS measures effective throughput (output tokens / total agent duration) which includes LLM inference time plus tool execution overhead. This represents real-world agent performance. Workflow Average TPS is typically lower because it also includes gaps between agent executions (state updates, inter-agent I/O). Both metrics provide complete visibility into system performance.

![Performance Metrics Dashboard](./docs/images/07-metrics.png)

Metrics are displayed in the agent logs panel upon completion with the format: `AgentName: total=X (out=Y), Zms, outTPS=W` showing total tokens, output tokens, duration, and output tokens per second for each agent, plus workflow-level averages.

