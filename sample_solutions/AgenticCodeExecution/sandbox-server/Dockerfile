ARG PYTHON_BASE_IMAGE=public.ecr.aws/docker/library/python:3.12-slim
FROM ${PYTHON_BASE_IMAGE}

ARG CODE_MODE_PIP_SPEC=git+https://github.com/universal-tool-calling-protocol/code-mode.git#subdirectory=python-library

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
COPY sandbox-server/requirements.txt /app/sandbox-server-requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir -r /app/sandbox-server-requirements.txt \
    && pip install --no-cache-dir "${CODE_MODE_PIP_SPEC}"

COPY sandbox-server /app/sandbox-server
WORKDIR /app/sandbox-server

EXPOSE 5051

CMD ["python", "mcp_server_codemode.py", "--host", "0.0.0.0", "--port", "5051", "--tools-url", "http://tools-server:5050/sse"]
