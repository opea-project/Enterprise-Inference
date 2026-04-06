# Fine-Tuning API Service

OpenAI-compatible LLM fine-tuning API service with Nvidia/Unsloth backend. Deploy with just a few commands!

## 🚀 Quick Start

Deploy in 2 simple steps:

```bash
# Step 1: Run interactive setup (auto-generates passwords, asks only what's needed)
./scripts/setup.sh

# Step 2: Deploy to Kubernetes
./scripts/deploy.sh
```

That's it! Your API will be available at `https://YOUR_DOMAIN/enterprise-ai/*`

---

## Prerequisites

- Kubernetes cluster with kubectl configured
- Helm 3.x installed
- Training backend server (Nvidia/Unsloth API server)
- **TLS Certificates**: Prepare your SSL/TLS certificates
  - Certificate file: `tls.crt` (or `cert.pem`, `fullchain.pem`)
  - Private key file: `tls.key` (or `key.pem`, `privkey.pem`)
  - You'll be asked for the path during setup (default: `./certs/`)
  - The deploy script will automatically create a Kubernetes TLS secret from these files
- Ingress controller (e.g., nginx-ingress)

**What gets auto-deployed:**
- ✅ PostgreSQL database (via Helm chart)
- ✅ Fine-Tuning API application
- ✅ Ingress with automatic TLS certificates

---

## Detailed Setup Instructions

### Step 1: Run Interactive Setup

The setup script will ask you for:
- Training backend URL and API key
- Your domain name
- Kubernetes namespace (optional)

Everything else (PostgreSQL password, Redis password, JWT secret) is **auto-generated securely**.

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

**What it does:**
1. ✓ Prompts for external service credentials (Training Backend, Domain)
2. ✓ Auto-generates secure passwords (PostgreSQL, JWT)
3. ✓ Creates `.env` file with all configuration
4. ✓ Updates Helm values with your domain

### Step 2: Deploy

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

**What it does:**
1. ✓ Validates configuration
2. ✓ Creates Kubernetes namespace
3. ✓ Deploys PostgreSQL database
4. ✓ Builds Docker image with Kaniko
5. ✓ Deploys the Fine-Tuning API
6. ✓ Initializes database schema with base models
7. ✓ Sets up Ingress with TLS

### Step 3: Verify

```bash
# Check pods are running
kubectl get pods -n finetuning

# View logs
kubectl logs -f deployment/finetuning-service -n finetuning

# Test the API
curl https://YOUR_DOMAIN/enterprise-ai/api/health
```

---

## What You Need to Provide

### Required Information

| What | Where to Get It | Example |
|------|----------------|---------|
| **Training Backend URL** | Your Nvidia/Unsloth server | `https://training.example.com:8443` |
| **Training Backend API Key** | Training server admin | `nvapi-xxxxx` |
| **Domain Name** | Your domain registrar | `mycompany.com` |
| **TLS Certificates** | SSL cert provider | `./certs/tls.crt` and `tls.key` |

### Auto-Generated (by setup.sh)

- PostgreSQL password (32 chars, random)
- JWT secret key (64 chars, random)

---

## API Endpoints

Once deployed, your API will support:

### Fine-Tuning Jobs
- `POST /v1/fine_tuning/jobs` - Create fine-tuning job
- `GET /v1/fine_tuning/jobs` - List all jobs
- `GET /v1/fine_tuning/jobs/{job_id}` - Get job status
- `GET /v1/fine_tuning/jobs/{job_id}/events` - Get job events
- `POST /v1/fine_tuning/jobs/{job_id}/cancel` - Cancel job

### Models
- `GET /v1/models` - List available base models for fine-tuning
- `GET /v1/models/{model_id}` - Get model details

**Full API Documentation:** `https://YOUR_DOMAIN/enterprise-ai/api/docs`

---

## Manual Configuration (Advanced)

If you prefer not to use the interactive setup:

1. Copy `.env.example` to `.env`
2. Edit `.env` and set all required values
3. Generate passwords:
   ```bash
   # PostgreSQL password
   openssl rand -base64 32

   # JWT secret
   openssl rand -base64 48
   ```
4. Update `helm-charts/finetuning-api/values.yaml` with your domain
5. Run `./scripts/deploy.sh`

See [CONFIGURATION.md](./CONFIGURATION.md) for detailed manual setup instructions.

---

## Project Structure

```
./                         # Project root
├── app/                    # FastAPI application code
│   ├── main.py            # Application entry point and startup
│   ├── config.py          # Configuration management
│   ├── schemas.py         # Pydantic models
│   ├── auth.py            # Keycloak JWT authentication
│   ├── database.py        # SQLAlchemy async database setup
│   ├── errors.py          # Error types and exception handlers
│   ├── observability.py   # Prometheus metrics and structured logging
│   ├── middleware.py      # Request size, CORS, rate limit middleware
│   ├── middleware/        # Middleware package
│   │   └── correlation.py # Correlation ID propagation
│   ├── adapters/          # Backend adapter pattern
│   │   ├── base.py        # Abstract adapter interface
│   │   ├── factory.py     # Adapter factory
│   │   └── resources/
│   │       └── nvidia_adapter.py  # Nvidia/Unsloth backend
│   ├── routers/           # API route handlers
│   │   ├── health.py      # Health check endpoints
│   │   ├── jobs.py        # Fine-tuning job endpoints
│   │   └── models.py      # Model listing endpoints
│   ├── security/          # AI/ML security controls
│   │   ├── model_protection.py    # Extraction rate limiting
│   │   └── model_watermarking.py  # Model ownership watermarks
│   ├── sql/               # Database schema
│   │   └── init-db.sql    # Schema with base models
│   ├── utils/             # Shared utilities
│   │   └── backend_auth.py  # Keycloak client-credentials auth
│   └── validators/        # Input validation
│       └── training_data_validator.py  # Injection pattern scanner
├── helm-charts/           # Kubernetes Helm charts
│   ├── finetuning-api/    # Main application chart
│   │   ├── values.yaml    # Configuration (set your domain here)
│   │   └── templates/     # Kubernetes manifests
│   └── postgresql/        # PostgreSQL chart
├── kaniko/                # Container build configuration
│   ├── kaniko-job.yaml    # Kaniko build job
│   └── deploy-finetuning.sh  # Build script
├── scripts/               # Deployment scripts ⭐
│   ├── setup.sh           # Interactive setup script
│   └── deploy.sh          # Kubernetes deployment script
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests
├── .env.example           # Configuration template
├── Dockerfile             # Application container
├── init-db.sql            # Database schema (root copy)
├── requirements.txt       # Python dependencies
├── requirements-test.txt  # Test dependencies
├── pytest.ini             # Pytest configuration
└── README.md              # This file
```

---

## Troubleshooting

### Configuration Issues

**Error: "Missing required variables"**
```bash
# Run setup again
./scripts/setup.sh
```

**Error: "example.com" or default values still present**
```bash
# Check your .env file
cat .env | grep -E "BASE_DOMAIN|NVIDIA_API_URL"

# If needed, run setup again
./scripts/setup.sh
```

### Deployment Issues

**Pods in CrashLoopBackOff**
```bash
# Check logs
kubectl logs -f deployment/finetuning-service -n finetuning

# Common causes:
# - Database not ready: Wait for PostgreSQL pod to be Ready
# - Wrong credentials: Verify .env file
```

**Database connection errors**
```bash
# Check PostgreSQL is running
kubectl get pods -n finetuning | grep postgresql

# Check password in secret
kubectl get secret finetuning-service-secret -n finetuning -o jsonpath='{.data.database-url}' | base64 -d
```

**Training backend connection errors**
```bash
# Test API connectivity
curl https://YOUR_DOMAIN/enterprise-ai/api/health

# Check API key
kubectl get secret finetuning-service-secret -n finetuning -o jsonpath='{.data.nvidia-api-key}' | base64 -d

# Test backend directly
kubectl exec -it deployment/finetuning-service -n finetuning -- curl -v $NVIDIA_API_URL/health
```

**Ingress/TLS issues**
```bash
# Check ingress
kubectl get ingress -n finetuning
kubectl describe ingress finetuning-service -n finetuning

# Verify TLS secret
kubectl get secret finetuning-api-tls -n finetuning
```

### Useful Commands

```bash
# View all resources
kubectl get all -n finetuning

# Get detailed pod info
kubectl describe pod -l app=finetuning-service -n finetuning

# Access PostgreSQL
kubectl exec -it finetuning-service-postgresql-0 -n finetuning -- psql -U finetuning -d finetuning

# Port-forward for local testing
kubectl port-forward -n finetuning svc/finetuning-service 8000:8000

# Check logs of all pods
kubectl logs -f -l app=finetuning-service -n finetuning --all-containers=true

# Restart deployment
kubectl rollout restart deployment/finetuning-service -n finetuning
```

---

## Security & Authentication

### Keycloak Integration

This API uses **Keycloak** for authentication and authorization. All API requests require a valid JWT token from Keycloak.

#### How Authentication Works:

1. **User Login:** Users authenticate through Keycloak UI
2. **Token Issuance:** Keycloak issues a JWT access token
3. **API Requests:** Client sends token in `Authorization: Bearer <token>` header
4. **Token Validation:** API validates token using Keycloak's JWKS endpoint

#### Getting a Token:

```bash
# Get token using password grant (for testing)
TOKEN=$(curl -X POST "https://YOUR_DOMAIN/realms/finetuning/protocol/openid-connect/token" \
  -d "client_id=finetuning-ui" \
  -d "username=your-username" \
  -d "password=your-password" \
  -d "grant_type=password" | jq -r '.access_token')

# Use token in API requests
curl -H "Authorization: Bearer $TOKEN" \
  https://YOUR_DOMAIN/enterprise-ai/v1/fine_tuning/jobs
```

#### Keycloak Configuration:

- **Realm:** `finetuning`
- **Client ID:** `finetuning-ui` (Public client)
- **Token Validation:** JWKS-based (no shared secrets)
- **User Identity:** Extracted from JWT `sub` claim

### APISIX Gateway Integration (Optional)

For enterprise deployments with centralized API gateway:

#### Enable APISIX Mode:

Edit `helm-charts/finetuning-api/values.yaml`:
```yaml
# Disable Nginx Ingress
ingress:
  enabled: false

# Enable APISIX
apisix:
  enabled: true
  oidc:
    enabled: true
    realm: "finetuning"
    client_id: "finetuning-ui"
    discovery: "https://YOUR_DOMAIN/realms/finetuning/.well-known/openid-configuration"
    use_jwks: true
```

#### APISIX Benefits:

- ✅ Centralized authentication across multiple services
- ✅ Token validation at gateway level (reduces load on backend)
- ✅ Unified API routing for LLM models, Fine-tuning, and Dataprep
- ✅ Built-in rate limiting and security policies

#### Traffic Flow (APISIX Mode):

```
User → APISIX Gateway → Token Validation (Keycloak JWKS) → Fine-Tuning API
```

### Security Best Practices

#### ✅ DO

- Use Keycloak for all authentication (no custom user management)
- Validate JWT tokens on every request
- Use HTTPS/TLS for all communications
- Rotate Keycloak client secrets regularly
- Enable RBAC in Keycloak for fine-grained permissions
- Use strong passwords for database (auto-generated by setup.sh)
- Keep `.env` file secure (it's in `.gitignore`)

#### ❌ DON'T

- Never commit `.env` file to git
- Don't bypass authentication for "convenience"
- Don't expose services without TLS
- Don't share JWT tokens or API keys publicly
- Don't use default/example passwords in production

---

## Updating the Deployment

To update with new code:

```bash
# Pull latest code
git pull

# Rebuild and redeploy
./scripts/deploy.sh
```

To change configuration:

```bash
# Edit .env file
nano .env

# Redeploy
./scripts/deploy.sh
```

---

## Uninstallation

```bash
# Remove Helm releases
helm uninstall finetuning-service -n finetuning
helm uninstall finetuning-service-postgresql -n finetuning

# Delete namespace (removes all resources)
kubectl delete namespace finetuning
```

---

## Support & Documentation

For issues or questions:
1. Check deployment logs: `kubectl logs -f deployment/finetuning-service -n finetuning`
2. Verify configuration: `cat .env`
3. Check Kubernetes resources: `kubectl get all -n finetuning`
4. Review API documentation: `https://YOUR_DOMAIN/enterprise-ai/api/docs`

---

## Architecture

### Components:

- **FastAPI Application:** OpenAI-compatible REST API
- **PostgreSQL:** Job state and base models storage
- **Keycloak:** Authentication and user management
- **Nginx/APISIX:** Ingress and API gateway
- **Nvidia/Unsloth Backend:** Actual fine-tuning execution

### Data Flow:

```
User (JWT) → API Gateway → Fine-Tuning API → PostgreSQL (job state)
                                          → Nvidia Backend (training)
```

---

## License

Proprietary
