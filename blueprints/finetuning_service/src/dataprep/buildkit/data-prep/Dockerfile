FROM python:3.11-slim

# Proxy build args (set only when behind a proxy; passed via --opt=build-arg at build time)
ARG http_proxy
ARG https_proxy
ARG no_proxy
ENV http_proxy=${http_proxy} \
    https_proxy=${https_proxy} \
    no_proxy=${no_proxy}

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