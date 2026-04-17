# Data Preparation Backend

A FastAPI-based backend for processing documents and generating fine-tuning training data using Docling, LlamaIndex, and Celery.

## Overview

Converts documents (PDF, DOCX, PPTX, TXT) into high-quality Q&A training data for LLM fine-tuning through a multi-stage processing pipeline.

**Key Features:**
- File upload/management via REST API
- Document to Markdown conversion (Docling)
- Q&A pair generation using LlamaIndex + External LLM
- Async parallel processing with Celery
- PostgreSQL metadata storage
- MinIO object storage
- Redis task queue
- Keycloak Based Authentication

## Architecture

```
Client (REST API)
    ↓
FastAPI Server (/v1/files, /v1/dataprep, /v1/jobs)
    ↓
Celery Workers (dataprep_queue)
    │
    ├── Docling Task: PDF/DOCX/PPTX → Markdown
    ├── LlamaIndex Task: Markdown → Q&A Pairs (via External LLM)
    └── Aggregator Task: Merge all Q&A into single JSONL
    ↓
Storage: MinIO (files) + PostgreSQL (metadata) + Redis (queue)
```

**Core Components:**
- **FastAPI**: REST API server
- **PostgreSQL**: File metadata storage
- **Celery Workers**: Async document processing
- **Redis**: Task queue broker
- **MinIO**: Object storage
- **Docling**: Document → Markdown converter
- **LlamaIndex**: Q&A generation engine
- **External LLM**: Training data generation

## Directory Structure

```
dataprep/
├── main.py                      # FastAPI entry point
├── requirements.txt
├── core/
│   ├── config/                  # Settings & database config
│   ├── handlers/                # File, storage, metadata, auth handlers
│   ├── routes/                  # API endpoints (files, dataprep, jobs)
│   ├── schemas/                 # Pydantic & SQLAlchemy models
│   ├── celery/                  # Celery config & tasks
│   └── utils/                   # Helper utilities
└── helmcharts/                  # Kubernetes deployments
```

## Processing Pipeline

**3-Stage Celery Chord Pattern:**

1. **Docling Conversion** (Parallel per file)
   - Download file from MinIO
   - Convert PDF/DOCX/PPTX → Markdown
   - Upload .md to MinIO

2. **LlamaIndex Q&A Generation** (Parallel per file)
   - Download .md from MinIO
   - Generate Q&A pairs via External LLM
   - Filter by quality threshold (default: 8.5/10)
   - Upload .jsonl to MinIO

3. **Aggregation** (Single task)
   - Merge all .jsonl files
   - Upload final training dataset
   - Update PostgreSQL metadata

**Supported File Types:** PDF, DOCX, PPTX, TXT, JSON, JSONL, TAR.GZ

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 13+
- Redis 6+
- MinIO or S3
- External LLM API (OpenAI-compatible)
- Llama3.3-70b for fine quality extraction of qa pairs in jsonl

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/dataprep
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/0
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin
export MINIO_BUCKET_NAME=dataprep
export OPENAI_API_BASE=https://your-llm-endpoint.com/v1
export OPENAI_API_KEY=your-api-key
export MODEL_NAME=your-model-name
```

### Running

**Terminal 1 - API Server:**
```bash
python main.py
```

**Terminal 2 - Celery Worker:**
```bash
celery -A core.celery.celery_config worker --loglevel=info --queue=dataprep_queue
```

**Access API Docs:** `http://localhost:8010/docs`

## API Endpoints

### Authentication

```bash
# Generate token
Need to update keycloak token fetch
```

### Files (`/v1/files`)

**Upload File:**
```bash
POST /v1/files
Content-Type: multipart/form-data
Body: file=@document.pdf, purpose=finetuning
```

**List Files:**
```bash
GET /v1/files
```

**Get File:**
```bash
GET /v1/files/{file_id}
```

**Delete File:**
```bash
DELETE /v1/files/{file_id}
```

### Data Preparation (`/v1/dataprep`)

**Submit Job:**
```bash
POST /v1/dataprep
Body: {"file_ids": ["file_123"], "quality_threshold": 8.5}
Response: {"submitted_job_ids": ["celery-task-id"], "job_status": "Submitted"}
```

**Check Status:**
```bash
GET /v1/dataprep/status/{job_id}
Response: {"job_status": "SUCCESS", "result": {...}}
```

### Jobs (`/v1/jobs`)

**List All Jobs:**
```bash
GET /v1/jobs
Response: {"user_id": "...", "total_jobs": 5, "jobs": [...]}
```

## Configuration

**Required Environment Variables:**
```bash
DATABASE_URL              # PostgreSQL connection string
CELERY_BROKER_URL         # Redis broker URL
CELERY_RESULT_BACKEND     # Redis result backend
MINIO_ENDPOINT            # MinIO server
MINIO_ACCESS_KEY          # MinIO credentials
MINIO_SECRET_KEY
MINIO_BUCKET_NAME         # Storage bucket
OPENAI_API_BASE           # External LLM endpoint
OPENAI_API_KEY            # LLM API key
MODEL_NAME                # LLM model identifier
```

## Storage Structure

**MinIO Bucket:**
```
dataprep/
└── {user_id}/
    ├── {file_id}.pdf           # Original file
    ├── {file_id}.md            # Markdown (Docling output)
    ├── {file_id}.jsonl         # Q&A pairs (LlamaIndex output)
    └── aggregated_{ts}.jsonl   # Final training data
```

**PostgreSQL:**
- `file_metadata` table: Stores file info, status, and metadata as JSONB

## Output Format

**Training Data (JSONL):**
```jsonl
{"instruction": "What is...?", "output": "The document...", "input": ""}
{"instruction": "How does...?", "output": "It works by...", "input": ""}
```

## Deployment

**Kubernetes/Helm:**
```bash
# Deploy all components
helm install postgres ./helmcharts/postgres/
helm install redis ./helmcharts/redis-broker/
helm install minio ./helmcharts/minio-data-store/
helm install dataprep-api ./helmcharts/data-prep-backend/
helm install celery-worker ./helmcharts/celery-worker/
```

## Support

- **API Docs:** `http://localhost:8010/docs`
- **Logs:** Check application and worker stdout/stderr
- **Configuration:** Review environment variables in `.env`
