FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for Docling PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb1 \
    libxrender1 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements-celery.txt .
RUN pip install --no-cache-dir -r requirements-celery.txt

# Copy the entire dataprep application
COPY . .

# Create non-root user to avoid running as root (DS-0002 / CIS Docker Benchmark)
RUN groupadd --gid 1000 appuser \
 && useradd --uid 1000 --gid 1000 --no-create-home --shell /bin/bash appuser \
 && chown -R appuser:appuser /app

USER appuser

# Run Celery worker
CMD ["celery", "-A", "core.celery.celery_config.celery_app", "worker", "--loglevel=info", "--concurrency=4", "--max-tasks-per-child=10", "--prefetch-multiplier=1", "-Q", "dataprep_queue"]
