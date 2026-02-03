## PDF to Podcast Generator

AI-powered application that transforms PDF documents into engaging podcast-style audio conversations using enterprise inference endpoints for script generation and OpenAI TTS for audio synthesis.

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

PDF to Podcast Generator is a microservices-based application that converts PDF documents into natural podcast-style audio conversations. The system extracts text from PDFs, generates engaging dialogue using Large Language Models, and synthesizes high-quality audio using Text-to-Speech technology.

---

## Features

- Digital PDF text extraction with support for text-based PDFs up to 10 MB
- AI-powered script generation with natural host and guest conversation format
- Enterprise inference endpoints for LLM-based script generation
- High-quality audio generation using OpenAI TTS with 6 different voice options
- Modern React web interface with real-time progress tracking
- Integrated audio player with waveform visualization
- Project management and organization with download functionality
- RESTful API for integration with JSON-based communication

---

## Architecture

This application uses a microservices architecture where each service handles a specific part of the podcast generation process. The React frontend communicates with a backend gateway that orchestrates requests across three specialized services: PDF processing, script generation, and audio synthesis. The LLM service uses enterprise inference endpoints with token-based authentication for script generation, while the TTS service uses OpenAI TTS API for audio generation. This separation allows for flexible deployment options and easy scaling of individual components.

```mermaid
graph TB
    subgraph "Client Layer"
        A[React Web UI<br/>Port 3000]
    end

    subgraph "API Gateway Layer"
        B[Backend Gateway<br/>Port 8000]
    end

    subgraph "Processing Services"
        C[PDF Service<br/>Port 8001]
        D[LLM Service<br/>Port 8002]
        E[TTS Service<br/>Port 8003]
    end

    subgraph "External Services"
        F[Enterprise Inference API]
        G[OpenAI TTS]
    end

    A -->|HTTP POST| B
    B -->|PDF Upload| C
    B -->|Script Request| D
    B -->|Audio Request| E
    C -->|Extracted Text| B
    D -->|API Request| F
    F -->|Script| D
    D -->|Dialogue Script| B
    E -->|API Request| G
    G -->|Audio Segments| E
    E -->|Mixed Audio| B
    B -->|JSON Response| A

    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#ffe1f5
    style D fill:#ffe1f5
    style E fill:#ffe1f5
    style F fill:#e1ffe1
    style G fill:#e1ffe1
```

This application is built using FastAPI microservices architecture with Docker containerization.

**Service Components:**

1. **React Web UI (Port 3000)** - Handles file uploads, displays generation progress, and provides audio playback interface

2. **Backend Gateway (Port 8000)** - Routes requests to microservices and manages job lifecycle and state

3. **PDF Service (Port 8001)** - Extracts text from PDF files using PyPDF2 and pdfplumber libraries (no external API dependencies)

4. **LLM Service (Port 8002)** - Generates podcast dialogue scripts using enterprise inference endpoints with token-based authentication

5. **TTS Service (Port 8003)** - Synthesizes audio using OpenAI TTS API with multiple voice support and audio mixing

---

## Prerequisites

### System Requirements

Before you begin, ensure you have the following installed:

- **Docker and Docker Compose**
- **Enterprise inference endpoint access** (token-based authentication)

### Verify Docker Installation

```bash
# Check Docker version
docker --version

# Check Docker Compose version
docker compose version

# Verify Docker is running
docker ps
```

### Required API Keys

**For LLM Service (Script Generation):**

This application supports multiple inference deployment patterns:

- **GenAI Gateway**: Provide your GenAI Gateway URL and API key
- **APISIX Gateway**: Provide your APISIX Gateway URL and authentication token

Configuration requirements:
- INFERENCE_API_ENDPOINT: URL to your inference service (GenAI Gateway, APISIX Gateway, etc.)
- INFERENCE_API_TOKEN: Authentication token/API key for your chosen service

**For TTS Service (Audio Generation):**

OpenAI API Key for text-to-speech:
- Sign up at https://platform.openai.com/
- Create API key at https://platform.openai.com/api-keys
- Key format starts with `sk-proj-`
- Requires access to TTS APIs

### Local Development Configuration

**For Local Testing Only**

If you're testing with a local inference endpoint using a custom domain (e.g., `inference.example.com` mapped to localhost in your hosts file):

1. Edit `api/llm-service/.env` and set:
   ```bash
   LOCAL_URL_ENDPOINT=inference.example.com
   ```
   (Use the domain name from your INFERENCE_API_ENDPOINT without `https://`)

2. This allows Docker containers to resolve your local domain correctly.

**Note:** For public domains or cloud-hosted endpoints, leave the default value `not-needed`.

---

## Quick Start Deployment

### Clone the Repository

```bash
git clone https://github.com/opea-project/Enterprise-Inference.git
cd sample_solutions/PDFToPodcast
```

### Set up the Environment

Each service needs its own `.env` file. Copy the example files and edit with your credentials.

**1. PDF Service Configuration:**

```bash
cp api/pdf-service/.env.example api/pdf-service/.env
```

No changes needed. Uses default values.

**2. TTS Service Configuration:**

```bash
cp api/tts-service/.env.example api/tts-service/.env
```

Open `api/tts-service/.env` and replace `your-openai-api-key-here` with your actual OpenAI API key.

Available TTS voices: alloy, echo, fable, onyx, nova, shimmer. Default voices are alloy (host) and nova (guest).

**3. LLM Service Configuration:**

```bash
cp api/llm-service/.env.example api/llm-service/.env
```

Open `api/llm-service/.env` and configure your inference endpoint:

- Replace `INFERENCE_API_ENDPOINT` with your inference service URL (without /v1)
- Replace `INFERENCE_API_TOKEN` with your pre-generated bearer token
- Update `INFERENCE_MODEL_NAME` if different from default (deepseek-ai/DeepSeek-R1-Distill-Qwen-32B)

**4. Backend Service Configuration:**

```bash
cp .env.example .env
```
No changes needed. Uses default values.

### Running the Application

Start both API and UI services together with Docker Compose:

```bash
# From the PDFToPodcast directory
docker compose up --build

# Or run in detached mode (background)
docker compose up -d --build
```
The Backend will be available at: http://localhost:8000

The UI will be available at: http://localhost:3000

The LLM-service will be available at: http://localhost:8002

The PDF-service will be available at: http://localhost:8001

The TTS-service will be available at: http://localhost:8003

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
curl http://localhost:8002/health

# Check if containers are running
docker compose ps
```

## User Interface

**Using the Application**

Make sure you are at the localhost:3000 url

**Test the Application**

1. Upload a PDF file (max 10MB)
2. Wait for text extraction
3. Select host and guest voices
4. Click "Generate Script" and wait 15-30 seconds
5. Review generated script
6. Click "Generate Audio" and wait 30-60 seconds
7. Listen to your podcast

![Home Page](./ui/public/homepage.png)

![Upload PDF](./ui/public/upload_pdf.png)

![Select Voices](./ui/public/select_voices.png)

![Final Podcast](./ui/public/final_podcast_page.png)


### Stopping the Application


```bash
docker compose down
```

## Troubleshooting

For detailed troubleshooting guidance and solutions to common issues, refer to:

[TROUBLESHOOTING_and_ADDITIONAL_INFO.md](./TROUBLESHOOTING_and_ADDITIONAL_INFO.md)

## Additional Info

The following models have been validated with pdf-podcast:

| Model | Hardware |
|-------|----------|
| **deepseek-ai/DeepSeek-R1-Distill-Qwen-32B** | Gaudi |
| **Qwen/Qwen3-4B-Instruct-2507** | Xeon |
