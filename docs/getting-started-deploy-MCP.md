# Deploying MCP Servers on Enterprise Inference Stack

---

## Overview

This guide provides step-by-step instructions for deploying a FastMCP (Model Context Protocol) server on the Enterprise Inference Stack. By following this guide, you will create a containerized MCP server and deploy it on your Kubernetes cluster with enterprise-grade security and network accessibility.

The deployment process includes creating the MCP application, containerizing it with Docker, pushing it to a registry, and deploying it using Helm charts with OIDC-based authentication.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Implementation](#implementation)
4. [Containerization](#containerization)
5. [Registry and Image Management](#registry-and-image-management)
6. [Helm Chart Configuration](#helm-chart-configuration)
7. [OIDC Authentication Setup](#oidc-authentication-setup)
8. [Deployment](#deployment)
9. [Deploying Pre-Built MCP Server Images](#deploying-pre-built-mcp-server-images)
10. [Troubleshooting](#troubleshooting)
11. [References](#references)

---

## Architecture Overview

The Enterprise Inference Stack uses a **remote HTTP deployment model** for MCP servers. This deployment architecture provides:

- **Network Accessibility**: Your MCP server is accessible over HTTP/HTTPS endpoints
- **Multi-Client Support**: Multiple client applications can connect simultaneously
- **Enterprise Security**: OIDC-based authentication protects your service
- **Kubernetes-Native**: Runs on the Enterprise Inference Stack's Kubernetes cluster
- **Horizontal Scalability**: Scale seamlessly using Horizontal Pod Autoscaler (HPA) based on CPU and memory utilization

### Transport Protocol

- **Transport Type**: HTTP/HTTPS (Remote Deployment)
- **Default Port**: 8000
- **Base Path**: `/demo/mcp`
- **Health Check Endpoint**: `/health`
- **Protocol Model**: Streaming HTTP

## Prerequisites

Ensure you have the following prerequisites in place:

### Required Infrastructure

- Enterprise Inference Stack (configured with `deploy_keycloak_apisix=on` for OIDC authentication support)
- Docker runtime for image building and local testing
- Helm 3.x for chart-based deployments
- Container registry (private or public) for image storage

### Required Tools

- Python 3.12 or later
- pip package manager
- Docker CLI
- kubectl configured with cluster access
- Helm CLI

### Required Permissions

- Write access to container registry
- Cluster administrator privileges or appropriate RBAC permissions
- Access to OIDC provider configuration
- Access to Enterprise Inference Stack configuration repository

---

## Implementation

### Step 1: Create Your MCP Server Application

Create `my_mcp_server.py` with the following implementation:

```python
from fastmcp import FastMCP
from starlette.responses import JSONResponse

# Initialize the MCP server
mcp = FastMCP("My MCP Server")

@mcp.tool
def add_numbers(numbers: list[float]) -> str:
    """
    Adds a list of numbers and returns the result as a string.

    Args:
        numbers (list[float]): A list of numbers to be added.

    Returns:
        str: A message with the sum of the input numbers.

    Note:
        This tool should be used for all addition requests, regardless of complexity.
    """
    total = sum(numbers)
    return f"The sum is {total}"

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "healthy", "service": "My MCP Server"})

# Create ASGI application
app = mcp.http_app(path="/demo/mcp", stateless_http=True)
```

**Implementation Notes:**
- The `@mcp.tool` decorator exposes the `add_numbers` function as an MCP tool
- Custom health check endpoint enables Kubernetes liveness and readiness probes
- ASGI application is configured with the `/demo/mcp` base path for routing

### Step 2: Define Python Dependencies

Create `requirements.txt` with the following dependencies:

```
fastmcp<3
uvicorn
```

---

## Containerization

### Step 3: Create a Dockerfile

```dockerfile
# Use a lightweight Python base image
FROM python:3.12-slim

# Set up working directory
WORKDIR /app

# Copy dependencies first for Docker build caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the MCP server code and any application related files
COPY my_mcp_server.py .

# Expose the port used by the FastMCP server (8000)
EXPOSE 8000

# Run the server using uvicorn (ASGI)
#   my_mcp_server:app → means "from my_mcp_server.py import app"
#   host=0.0.0.0 so container is accessible externally
CMD ["uvicorn", "my_mcp_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build Configuration Details:**
- **Base Image**: `python:3.12-slim` for minimal footprint and security updates
- **Layer Optimization**: Dependencies layer placed before application code to leverage Docker build cache
- **Security**: Non-root execution recommended (implement in production environments)
- **Networking**: Host binding on `0.0.0.0` enables external accessibility within cluster

### Build Your Docker Image

Run the following command:

```bash
docker build -t my_mcp_server:latest .
```

**Options:**
- `-t my_mcp_server:latest`: Tags the image with repository and version
- Standard build context with Dockerfile in current directory

---

## Registry and Image Management

### Step 4: Push to Container Registry

Upload your image to your container registry:

```bash
docker tag my_mcp_server:latest <your_repository>/my_mcp_server:1.0.0
docker push <your_repository>/my_mcp_server:1.0.0
```

**Configuration Parameters:**
- `<your_repository>`: Replace with your container registry URL (e.g., `ecr.aws.com/my-org` or `gcr.io/my-project`)
- Image naming follows standard Docker registry conventions
- Ensure registry credentials are configured in your local Docker context

---

## Helm Chart Configuration

### Step 5: Update the Helm Chart Values

The MCP server helm chart is located in the [core/helm-charts/mcp-server-template/](../core/helm-charts/mcp-server-template/) directory.

Update the `values.yaml` file in this directory with your deployment configuration:

#### Update Container Image

```yaml
# values.yaml
image:
  repository: <your_repository>/my_mcp_server
  tag: "1.0.0"          # Use semantic versioning, never 'latest' in production
  pullPolicy: Always    # Always pull to ensure correct version with registry
  # pullSecrets: []
```

#### Service Configuration

```yaml
service:
  type: ClusterIP
  port: 8000
  targetPort: 8000
  annotations: {}
```

#### Ingress Configuration

```yaml
ingress:
  enabled: true
  className: "nginx"
  namespace: auth-apisix
  host: api.example.com  # Replace with your ingress hostname
  # MCP endpoint path - customize for your deployment
  path: /demo/mcp
  annotations:
    nginx.ingress.kubernetes.io/use-regex: "true"
    # Streaming-friendly settings for MCP Streamable HTTP (per MCP best practices)
    nginx.ingress.kubernetes.io/proxy-buffering: "off"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
  tls:
    enabled: true
    secretName: mcp-server-tls  # Replace with your TLS secret name
```

---

## OIDC Authentication Setup

### Step 6: Configure OpenID Connect (OIDC)

Configure OIDC to secure your MCP server with enterprise authentication:

#### OIDC Configuration Parameters

Update the OIDC settings in `values.yaml`:

```yaml
oidc:
  realm: master
  client_id: ""         # Update with value from generate-token.sh
  client_secret: ""     # Update with value from generate-token.sh
  discovery: http://keycloak.default.svc.cluster.local/realms/master/.well-known/openid-configuration
  introspection_endpoint: http://keycloak.default.svc.cluster.local/realms/master/protocol/openid-connect/token/introspect
```

### Step 7: Generate OIDC Credentials

Execute the helper script to generate ClientID and Client Secret:

```bash
source core/scripts/generate-token.sh
```

**Prerequisites:**

Before running the script, update the following environment variables in `core/scripts/generate-token.sh` according to your cluster configuration:

```bash
export BASE_URL="api.example.com"                               # Base URL of Keycloak server (without https://)
export KEYCLOAK_ADMIN_USERNAME="your-keycloak-admin-user"       # Keycloak admin username
export KEYCLOAK_PASSWORD="changeme"                             # Keycloak admin password
export KEYCLOAK_CLIENT_ID="my-client-id"                        # Client ID to be created in Keycloak
```

**Output:**

The script generates and displays the following values:

- `BASE_URL`: The base URL for your Keycloak server
- `KEYCLOAK_CLIENT_SECRET`: The confidential client secret for authentication
- `TOKEN`: Bearer token for API access (format: `bearer {TOKEN}`)

Copy these values and update the `values.yaml` file with the generated `clientId` and `clientSecret`.


---

## Deployment

### Step 8: Deploy Using Helm

You can deploy your MCP server to the Enterprise Inference Stack by running the following command from the root folder of the repository:

```bash
helm install mcp-server ./core/helm-charts/mcp-server-template \
  --namespace default \
  --set image.repository=<your_repository>/my_mcp_server \
  --set image.tag=1.0.0 \
  --set oidc.client_id=<your_client_id> \
  --set oidc.client_secret=<your_client_secret> \
  --set ingress.host=<your_ingress_host_name> \
  --set ingress.tls.secretName=<your_ingress_TLS_secret>
```

### Step 9: Verify Deployment

```bash
# Check pod status
kubectl get pods -n default -l app.kubernetes.io/instance=mcp-server

# Verify service status
kubectl get svc -n default -l app.kubernetes.io/instance=mcp-server

# Check ingress configuration
kubectl get ingress -n auth-apisix -l app.kubernetes.io/instance=mcp-server

# View pod logs
kubectl logs -n default -l app.kubernetes.io/instance=mcp-server -f

# Test health endpoint
curl https://<your_ingress_host_name>/health
```

### Step 10: Validate Functionality

Your MCP server is now accessible and ready to accept connections from MCP clients.

**Endpoint Details:**
- **URL**: `https://<your_ingress_host_name>/demo/mcp`
- **Authentication**: OIDC Bearer Token (from Step 7 output)
- **Protocol**: Streamable HTTP

**Connecting from an MCP Client:**

You can connect your deployed MCP server using any MCP-compatible client. The client should be able to discover and invoke the tools and actions exposed by your MCP server.

**Example: Using Flowise AI**

To connect your MCP server from Flowise AI or similar MCP clients, provide the following configuration:

```json
{
  "url": "https://<your_ingress_host_name>/demo/mcp",
  "headers": {
    "Authorization": "Bearer {{$vars.MCPAuthToken}}"
  }
}
```

Replace:
- `<your_ingress_host_name>`: Your actual ingress hostname (e.g., `api.example.com`)
- `{{$vars.MCPAuthToken}}`: Your OIDC bearer token (obtained from the `TOKEN` output in Step 7)

Once connected, you should be able to list and invoke the available tools and actions exposed by your MCP server.


---

## Deploying Pre-Built MCP Server Images

The MCP server helm chart is located in the [core/helm-charts/mcp-server-template/](../core/helm-charts/mcp-server-template/) directory.

To deploy any pre-built MCP server from Docker Hub or other registries, each server has its own specific configuration requirements:

1. Find the image repository (e.g., `mcp/brave-search`)
2. Check the server documentation for required environment variables and any secrets specific to that server
3. Use the same Helm deployment pattern, but replace the `env` parameters with the server's specific requirements—each MCP server will have different secrets and environment variables that must be properly configured
4. Ensure all required secrets (API keys, tokens, credentials, etc.) are set correctly before deployment

**Note**: The Helm chart has been designed and optimized for the **streamable HTTP transport protocol**. This ensures compatibility with any pre-built MCP server that uses HTTP-based communication, providing proper streaming support and connection management out of the box.

### Example: Brave Search MCP Server

Here's how to deploy the **Brave Search MCP Server** as a practical example.

**Docker Hub Repository**: https://hub.docker.com/r/mcp/brave-search

#### Deployment Command
Replace the placeholders with your values (OIDC credentials from Step 7, API keys, ingress hostname, etc.).

You can now deploy MCP server to the Enterprise Inference Stack by running the following command from the root folder of the repository:

```bash
export BRAVE_API_KEY="Your BRAVE_API_KEY"
helm install mcp-server ./core/helm-charts/mcp-server-template -n default \
  --set image.repository=mcp/brave-search \
  --set image.tag=latest \
  --set env[0].name=BRAVE_API_KEY \
  --set env[0].value="$BRAVE_API_KEY" \
  --set env[1].name=BRAVE_MCP_TRANSPORT \
  --set env[1].value="http" \
  --set env[2].name=BRAVE_MCP_PORT \
  --set-string env[2].value="8000" \
  --set env[3].name=BRAVE_MCP_HOST \
  --set env[3].value="0.0.0.0" \
  --set env[4].name=BRAVE_MCP_ENABLED_TOOLS \
  --set env[4].value="brave_news_search" \
  --set oidc.client_id=<your_client_id> \
  --set oidc.client_secret=<your_client_secret> \
  --set ingress.host=<your_ingress_host_name> \
  --set ingress.tls.secretName=<your_ingress_TLS_secret> \
  --set ingress.path=/mcp
```

Tip: Put your custom values in a file (for example `values.override.yaml`) and deploy with:

```bash
helm upgrade --install mcp-server mcp-server-template -n default -f values.override.yaml
```

Security: Do not store plaintext secrets in that file. Create Kubernetes `Secret` objects and reference them from `values.override.yaml`. Use `--set` or `--set-file` only for small, non-sensitive overrides when appropriate.

#### Verification

```bash
# Check pod status
kubectl get pods -n default -l app.kubernetes.io/instance=mcp-server

# View logs
kubectl logs -n default -l app.kubernetes.io/instance=mcp-server -f

# Access your MCP endpoint
https://<your-ingress-host>/mcp
```

---

## Troubleshooting

### Common Issues and Resolution

**Issue: ImagePullBackOff**
- **Cause**: Container image not accessible in registry
- **Resolution**: Verify image exists and registry credentials are configured in cluster

**Issue: CrashLoopBackOff**
- **Cause**: Application startup failure
- **Resolution**: Check pod logs via `kubectl logs <pod-name>`

**Issue: 401 Unauthorized on Endpoints**
- **Cause**: OIDC token invalid or misconfigured
- **Resolution**: Verify OIDC configuration and token validity

**Issue: Health Check Failures**
- **Cause**: Application not responding on `/health` endpoint
- **Resolution**: Verify application startup and port binding

---

## References

- [FastMCP HTTP Deployment Guide](https://gofastmcp.com/deployment/http)
- [FlowiseAI Tools & MCP](https://docs.flowiseai.com/tutorials/tools-and-mcp)
- [Docker Hub MCP Repositories](https://hub.docker.com/mcp/explore)

---
