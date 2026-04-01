ARG PYTHON_BASE_IMAGE=public.ecr.aws/docker/library/python:3.12-slim
FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
COPY tools-server/requirements.txt /app/tools-server-requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir -r /app/tools-server-requirements.txt

COPY tools-server /app/tools-server
WORKDIR /app/tools-server

EXPOSE 5050

CMD ["python", "mcp_retail_server.py", "--host", "0.0.0.0", "--port", "5050"]
