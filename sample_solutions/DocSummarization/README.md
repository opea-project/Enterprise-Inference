## Document Summarization

A full-stack document summarization application that processes text and document files to generate concise summaries with enterprise inference integration.

## Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start Deployment](#quick-start-deployment)
- [User Interface](#user-interface)
- [Troubleshooting](#troubleshooting)
- [Additional Info](#additional-info)

---

## Project Overview

The **Document Summarization** application processes multiple content formats to generate concise summaries. Users can paste text or upload documents (PDF, DOCX, TXT). The backend uses enterprise inference endpoints with token-based authentication for all text summarization operations.

---

## Features

**Backend**

- Multiple input format support (text, PDF, DOCX, TXT)
- PDF text extraction with OCR support for image-based PDFs
- DOCX document processing
- Enterprise inference integration with token-based authentication
- File validation and size limits (PDF/DOCX: 50 MB)
- CORS enabled for web integration
- Comprehensive error handling and logging
- Health check endpoints
- Modular architecture (routes + services)

**Frontend**

- Clean, intuitive interface with tab-based input selection
- Drag-and-drop file upload
- Real-time summary display
- Mobile-responsive design with Tailwind CSS
- Built with Vite for fast development

---

## Architecture

Below is the architecture showing how user input is processed through document extraction, then summarized using the enterprise inference endpoint.

```mermaid
graph TB
    A[React Web UI<br/>Port 5173] -->|User Input| B[FastAPI Backend<br/>Port 8000]

    B --> C{Input Type}
    C -->|Text| D[LLM Service]
    C -->|PDF/DOCX/TXT| E[Document Service]

    E -->|Extracted Text| D

    D -->|API Call with Token| F[Enterprise Inference<br/>Token-based Auth]
    F -->|Summary| B
    B -->|JSON Response| A

    style A fill:#e1f5ff
    style B fill:#fff4e1
    style D fill:#ffe1f5
    style E fill:#ffe1f5
    style F fill:#e1ffe1
```

The application consists of:
1. **Document Processing Service**: Extracts text from PDF, DOCX, and TXT files
2. **LLM Service**: Generates summaries using enterprise inference API
3. **API Layer**: FastAPI backend with token-based authentication
4. **UI**: React-based interface with Vite and Tailwind CSS

**Service Components:**

1. **React Web UI (Port 5173)** - Provides intuitive interface with drag-and-drop file upload, tab-based input selection, and real-time summary display

2. **FastAPI Backend (Port 8000)** - Orchestrates document processing, handles token-based authentication, and routes requests to appropriate processing services

**Typical Flow:**

1. User inputs text or uploads a document (PDF/DOCX/TXT) through the web UI.
2. The backend processes the input:
   - Text: Sent directly to LLM service
   - PDF/DOCX/TXT: Extracted using document service with OCR support
3. The LLM service uses the pre-configured token to call the enterprise inference endpoint.
4. The model generates a summary using the configured LLM (e.g., Llama-3.1-8B-Instruct).
5. The summary is returned and displayed to the user via the UI.

---

## Prerequisites

### System Requirements

Before you begin, ensure you have the following installed:

- **Docker and Docker Compose**
- **Enterprise inference endpoint access** (token-based authentication)

### Required API Configuration

**For Inference Service:**

This application supports multiple inference deployment patterns:

| API Configuration | Validated |
|---|:---:|
| GenAI Gateway | ✅ |
| Keycloak/APISIX | ✅ |

- **GenAI Gateway**: Provide your GenAI Gateway URL and API key
  - To generate the GenAI Gateway API key, use the [generate-vault-secrets.sh](https://github.com/opea-project/Enterprise-Inference/blob/main/core/scripts/generate-vault-secrets.sh) script
  - The API key is the `litellm_master_key` value from the generated `vault.yml` file
  
- **APISIX Gateway**: Provide your APISIX Gateway URL and authentication token
  - To generate the APISIX authentication token, use the [generate-token.sh](https://github.com/opea-project/Enterprise-Inference/blob/main/core/scripts/generate-token.sh) script
  - The token is generated using Keycloak client credentials

### Deploy Required Model(s)

The following models have been validated on different hardware platforms. At least one model must be deployed.

| Model | Xeon | Gaudi |
|---|:---:|:---:|
| **meta-llama/Llama-3.1-8B-Instruct** | ❌ | ✅ Validated on Dell XE7740 |
| **Qwen/Qwen3-4B-Instruct-2507** | ✅ Validated on Dell XE7740 | ❌ |

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
git clone https://github.com/opea-project/Enterprise-Inference.git
cd Enterprise-Inference/sample_solutions/DocSummarization
```

### Set up the Environment

This application requires an `.env` file in the root directory for proper configuration. Create it using [.env.example](./.env.example) with the commands below:

```bash
cp .env.example .env
```
Then modify it as needed, with special consideration to certain environment variables mentioned below. Read through the .env file for full instructions.

**Important Configuration Notes:**

- **INFERENCE_API_ENDPOINT**: Your actual inference service URL (replace `https://api.example.com`)
  - For APISIX/Keycloak deployments, the model name must be included in the endpoint URL (e.g., `https://api.example.com/Llama-3.1-8B-Instruct`)
- **INFERENCE_API_TOKEN**: Your actual pre-generated authentication token
- **INFERENCE_MODEL_NAME**: Use the exact model name from your inference service
  - To check available models: `curl https://api.example.com/v1/models -H "Authorization: Bearer your-token"`
- **LOCAL_URL_ENDPOINT**: Only needed if using local domain mapping (i.e. `api.example.com` mapped to localhost) for Docker containers to resolve correctly.
  - Use the domain name from INFERENCE_API_ENDPOINT without `https://`
  - For public domains or cloud-hosted endpoints, leave the default value `not-needed`
- **VERIFY_SSL**: Controls SSL certificate verification (default: `true`)
  - Set to `false` only for development environments with self-signed certificates
  - Keep as `true` for production environments

**Note**: The docker-compose.yaml file automatically loads environment variables from `.env` for the backend service.

### Running the Application

Start both API and UI services together with Docker Compose:

```bash
# From the DocSummarization directory
docker compose up --build

# Or run in detached mode (background)
docker compose up -d --build
```

The Backend will be available at: `http://localhost:8000`
The UI will be available at: `http://localhost:5173`

**View logs**:

```bash
# All services
docker compose logs -f

# Backend only
docker compose logs -f backend

# Frontend only
docker compose logs -f frontend
```

**Verify the services are running**:

```bash
# Check API health
curl http://localhost:8000/health

# Check if containers are running
docker compose ps
```

---

## User Interface

**Using the Application**

Make sure you are at the `http://localhost:5173` URL

You will be directed to the main page with the summarization interface

![Home Page - Hero Section](./assets/img/homepage.png)

![Document Summarization Interface](./assets/img/ui.png)

### Summarization Interface

1. Navigate to the summarization interface
2. Choose input method:
   - **Text Input**: Paste or type text directly
   - **File Upload**: Upload PDF, DOCX, or TXT files (drag-and-drop supported)
3. Click "Generate Summary" to process your content
4. View the generated summary in real-time

**UI Configuration**

When running with Docker Compose, the UI automatically connects to the backend API. The frontend is available at `http://localhost:5173` and the API at `http://localhost:8000`.

For production deployments, you may want to configure a reverse proxy or update the API URL in the frontend configuration.

### Stopping the Application

```bash
docker compose down
```

---

## Troubleshooting

For comprehensive troubleshooting guidance, common issues, and solutions, refer to:

[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
