# GPU Accelerated Fine-tuning Engine

Production-ready fine-tuning service for LLMs with GPU acceleration, built with FastAPI and Unsloth.

## Quick Start

### Prerequisites
- Docker- **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
- **NVIDIA GPU** (for training)
- **Ubuntu/Linux** (recommended)
- **SSL Certificates** (for production HTTPS deployment)

### Step 1: Clone
```bash
git clone <your-repo-url>
cd <your-repo-folder>
```

### Step 2: Configure Environment
```bash
cp .env.example .env
```

Edit `.env` and set:
- `API_KEY` (use `openssl rand -base64 32`)
- `FILES_API_URL`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `DATABASE_URL` (must match the above)
- `ENV`:
  - `development` for dev compose
  - `production` for HTTPS



## Development Mode (HTTP)

Uses [docker-compose-dev.yml](docker-compose-dev.yml) and HTTP on port 8000.

```bash
# Ensure ENV=development in .env
docker compose -f docker-compose-dev.yml up -d --build
```

API available at:
- http://localhost:8000
- http://localhost:8000/docs

---

## Production Mode (HTTPS)

Uses [docker-compose.yml](docker-compose.yml) and HTTPS on port 8443.

### Certificate Setup
The app requires these files (exact names):
- `certs/cacert.pem`
- `certs/private.key`

```bash
mkdir -p certs
cp /path/to/cacert.pem certs/
cp /path/to/private.key certs/
```

```bash
# Ensure ENV=production in .env
docker compose up -d --build
```

## Check the logs of container

```bash
docker logs -f finetune-api
```

API available at:
- https://your-domain.com:8443
- https://your-domain.com:8443/docs

---

##  Authentication
All API requests require `X-API-Key`.

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/info
```

---

## Usage Examples

### Start a Fine-tuning Job
```bash
curl -X POST "http://localhost:8000/finetune/start" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "user_uuid": "user-uuid-from-files-api",
    "model_name": "unsloth/llama-3-8b-bnb-4bit",
    "input_filenames": ["file-uuid-from-files-api"],
    "hyperparameters": {
      "num_train_epochs": 3,
      "learning_rate": 0.0002,
      "batch_size": 2,
      "max_seq_length": 2048
    }
  }'
```

### Check Job Status
```bash
curl -H "X-API-Key: your-api-key" \
  "http://localhost:8000/finetune/job/{job_id}"
```

### List Jobs
```bash
curl -H "X-API-Key: your-api-key" \
  "http://localhost:8000/finetune/jobs"
```

### GPU Status / Availability
```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/finetune/gpu-status
curl -H "X-API-Key: your-api-key" http://localhost:8000/finetune/availability
```

---

## Common Commands

### Docker Compose
```bash
# Dev
docker compose -f docker-compose-dev.yml up -d
docker compose -f docker-compose-dev.yml down

# Prod
docker compose up -d
docker compose down

# Logs
docker compose logs -f finetune-api
```

### Database
```bash
./scripts/verify_postgres.sh
docker compose exec postgres psql -U finetune -d finetune_db
docker compose logs -f postgres
```

---

##  Project Structure
```
.
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration (reads from .env)
│   ├── models.py            # Database models
│   ├── schemas.py           # Pydantic schemas
│   ├── routers/
│   │   └── jobs.py          # Job management endpoints
│   └── services/
│       ├── gpu_engine.py    # GPU training logic
│       └── file_client.py   # Files API integration
├── scripts/│
│           └── verify_postgres.sh
├── .env                     # Your configuration (git-ignored)
├── .env.example             # Environment template
├── docker-compose.yml       # HTTPS production services
├── docker-compose-dev.yml   # HTTP development services
├── Dockerfile               # API service image
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── POSTGRESQL_SETUP.md      # Detailed PostgreSQL guide
```

---

## Troubleshooting

### SSL Errors in Production
Ensure certificate filenames match:
- `certs/cacert.pem`
- `certs/private.key`

See [app/start.sh](app/start.sh).

### GPU Not Detected
```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### API Not Starting
```bash
docker compose logs finetune-api
```

---

##  Environment Variables Reference

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `ENV` | `development` or `production` | `development` | ✅ |
| `API_KEY` | Authentication key | `openssl rand -base64 32` | ✅ |
| `POSTGRES_USER` | PostgreSQL username | `finetune` | ✅ |
| `POSTGRES_PASSWORD` | PostgreSQL password | `secure_password` | ✅ |
| `POSTGRES_DB` | PostgreSQL database name | `finetune_db` | ✅ |
| `DATABASE_URL` | Full connection string | `postgresql+asyncpg://...` | ✅ |
| `FILES_API_URL` | Files service endpoint | `https://files.example.com` | ✅ |
| `MAX_CONCURRENT_JOBS` | Maximum parallel jobs | `1` | ✅ |
| `GPU_MEMORY_THRESHOLD_GB` | Min free GPU memory | `2.0` | ✅ |
| `DEFAULT_MAX_SEQ_LENGTH` | Default sequence length | `2048` | ✅ |
| `DEFAULT_BATCH_SIZE` | Default batch size | `2` | ✅ |
| `DEFAULT_GRADIENT_ACCUMULATION` | Gradient accumulation | `4` | ✅ |

---

## License
Apache 2.0
