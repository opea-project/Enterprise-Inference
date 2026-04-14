# Load environment variables before importing config
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from core.handlers.auth_handler import configure_openapi_auth

from core.config import settings
from core.middleware import limiter, RequestLoggingMiddleware, SecurityHeadersMiddleware, rate_limit_exceeded_handler
from core.routes import files_router, dataprep_router
from core.utils.database_utils import init_database, check_database_connection


app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    # APISIX rewrites ^/enterprise-ai/dataprep(.*) → $1 before forwarding to
    # this service.  root_path tells Starlette/Swagger the external prefix so
    # that "Try it out" URLs and Swagger's schema fetch are constructed as
    # https://<host>/enterprise-ai/dataprep/openapi.json — which APISIX then
    # routes correctly.  The docs_url/openapi_url values are what the backend
    # receives *after* the proxy strips the prefix (i.e. the bare paths).
    root_path=settings.API_BASE_PATH,      # /enterprise-ai/dataprep
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "docExpansion": "none",
        "persistAuthorization": True,
        "filter": True,
        "deepLinking": True,
        "displayRequestDuration": True,
    },
)

# -------------------------------------------------------------------
# Rate limiting  (global default: 100 req/min, set per-route for tighter limits)
# SlowAPIMiddleware applies the default_limits from the Limiter to ALL routes
# -------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# -------------------------------------------------------------------
# CORS middleware
# SECURITY FIX: wildcards ('*') cannot be used with allow_credentials=True -
# browsers block such responses per the CORS spec.
# Use an explicit per-origin allowlist from the ALLOWED_ORIGINS env var instead.
# -------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Correlation-ID"],
)

# Configure OpenAPI schema with Bearer authentication
app.openapi = lambda: configure_openapi_auth(app)

# Include routers
app.include_router(files_router)
app.include_router(dataprep_router)


@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup"""
    # Initialize database and tables (creates DB if doesn't exist)
    init_database()

    # Check database connection
    if not check_database_connection():
        raise RuntimeError("Failed to connect to PostgreSQL database. Please check your database configuration.")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT
    )
