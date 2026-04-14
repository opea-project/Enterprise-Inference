FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY dataprep/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire dataprep application
COPY dataprep/ .

# Create non-root user to avoid running as root (DS-0002 / CIS Docker Benchmark)
RUN groupadd --gid 1000 appuser \
 && useradd --uid 1000 --gid 1000 --no-create-home --shell /bin/bash appuser \
 && chown -R appuser:appuser /app

USER appuser

# Expose the default FastAPI port
EXPOSE 8000

# Start FastAPI app using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]