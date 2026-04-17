"""
Production Fine-Tuning Service API - Main Application

Enterprise-grade FastAPI service for fine-tuning large language models.
Optimized for production with security, performance, and maintainability.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded

# Import application modules
from .config import get_settings
from .database import db_manager
from .auth import AuthManager
from .middleware import SecurityHeadersMiddleware, RequestLoggingMiddleware, limiter, rate_limit_exceeded_handler
from .middleware.correlation import CorrelationIDMiddleware
from .observability import (
    configure_logging,
    get_logger,
    MetricsMiddleware,
    metrics_endpoint
)
from .errors import (
    OpenAIError,
    openai_error_exception_handler,
    validation_exception_handler,
    generic_exception_handler
)
from .adapters.base import ResourceAdapterFactory
from .routers import health_router, models_router, jobs_router

# Load settings
settings = get_settings()

# Configure structured logging
configure_logging()
logger = get_logger(__name__)

# Global auth manager
auth_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown"""
    global auth_manager
    
    logger.info("=" * 70)
    logger.info("🚀 Starting Fine-Tuning Service")
    logger.info(f"   Environment: {settings.environment.value}")
    logger.info(f"   Version: {settings.api.version}")
    logger.info(f"   Log Level: {settings.log_level.value}")
    logger.info("=" * 70)
    
    try:
        # Initialize database
        logger.info("📊 Initializing database connection pool...")
        await db_manager.initialize(
            database_url=settings.database.url,
            min_size=settings.database.pool_min_size,
            max_size=settings.database.pool_max_size,
            timeout=settings.database.pool_timeout,
            command_timeout=settings.database.command_timeout
        )
        logger.info("   ✓ Database initialized")
        
        # Initialize authentication
        logger.info("🔐 Initializing authentication manager...")
        import app.auth as auth_module
        auth_module.auth_manager = AuthManager(settings.keycloak.issuer)
        auth_manager = auth_module.auth_manager
        logger.info("   ✓ Authentication initialized")
        
        # Initialize adapter factory
        logger.info("🔌 Initializing resource adapter factory...")
        ResourceAdapterFactory.initialize(db_manager.pool)
        logger.info("   ✓ Adapter factory initialized")
        
        logger.info("=" * 70)
        logger.info("✅ Fine-Tuning Service startup completed successfully")
        logger.info(f"📡 API available at: {settings.api.base_path}")
        logger.info(f"📚 Docs available at: {settings.api.base_path}/api/docs")
        logger.info("=" * 70)
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}", exc_info=True)
        raise
    
    # Shutdown
    logger.info("🛑 Shutting down Fine-Tuning Service...")
    await db_manager.close()
    logger.info("✅ Shutdown completed")


# Create FastAPI application
app = FastAPI(
    title=settings.api.title,
    description=settings.api.description,
    version=settings.api.version,
    lifespan=lifespan,
    root_path=settings.api.base_path,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    swagger_ui_parameters={
        "docExpansion": "none",
        "persistAuthorization": True,
        "filter": True,
        "deepLinking": True,
        "displayRequestDuration": True
    }
)

# Set maximum request size to prevent DoS (100MB)
app.state.max_request_size = 100 * 1024 * 1024

# Add middlewares (order matters - LIFO execution)
if settings.observability.enabled and settings.observability.metrics_enabled:
    app.add_middleware(MetricsMiddleware)

# Security middlewares
app.add_middleware(CorrelationIDMiddleware)  # Add correlation IDs for tracing
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=settings.api.cors_allow_credentials,
    allow_methods=settings.api.cors_allow_methods,
    allow_headers=settings.api.cors_allow_headers,
    expose_headers=settings.api.cors_expose_headers,
)

# Add rate limiter state
app.state.limiter = limiter

# Register exception handlers
app.add_exception_handler(OpenAIError, openai_error_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include routers
app.include_router(health_router)
app.include_router(models_router)
app.include_router(jobs_router)

# Prometheus metrics endpoint (no auth required for scraping)
if settings.observability.enabled and settings.observability.metrics_enabled:
    @app.get("/metrics", tags=["Monitoring"], include_in_schema=False)
    async def get_metrics(request: Request):
        """Prometheus metrics endpoint for monitoring and user tracking"""
        return await metrics_endpoint(request)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """API root endpoint"""
    return {
        "service": "Fine-Tuning API",
        "version": settings.api.version,
        "docs": f"{settings.api.base_path}/api/docs",
        "health": f"{settings.api.base_path}/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.log_level.value.lower()
    )
