# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
import logging
import time
from datetime import datetime

from app.routers import jobs_router
from app.database import db_engine, Base
from app.config import settings, GPU_INFO
from app.limiter import limiter

# Configure logging
logger = logging.getLogger("uvicorn")


# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add OWASP-recommended security headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
        return response


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="Production-grade LLM fine-tuning service using Unsloth on NVIDIA GPUs",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Attach rate-limiter state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers on every response
app.add_middleware(SecurityHeadersMiddleware)

# CORS – origins are driven by the ALLOWED_ORIGINS environment variable so
# that production deployments are never accidentally left with wildcard access.
_allowed_origins = [
    origin.strip()
    for origin in settings.ALLOWED_ORIGINS.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs_router)

# Middleware for request logging and timing
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")

    try:
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        # Log response
        logger.info(
            f"Response: {request.method} {request.url.path} "
            f"Status: {response.status_code} Time: {process_time:.3f}s"
        )

        return response
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url.path} Error: {e}")
        raise

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.ENV == "dev" else "An unexpected error occurred"
        }
    )

@app.on_event("startup")
async def startup():
    """Initialize application on startup"""
    logger.info(f"Starting {settings.APP_NAME} v2.0.0")
    logger.info(f"Environment: {settings.ENV}")

    # Log GPU information
    if GPU_INFO.get("available"):
        logger.info(f"GPU detected: {GPU_INFO.get('name')} ({GPU_INFO.get('total_memory_gb'):.2f} GB)")
    else:
        logger.warning("WARNING: No GPU detected! This service requires NVIDIA GPU.")

    # Create database tables
    try:
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    # Clean up orphaned jobs from previous shutdown
    try:
        from app.database import AsyncSessionLocal
        from app.models import TrainingJob
        from sqlalchemy.future import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TrainingJob).where(TrainingJob.status.in_(["RUNNING", "PENDING"]))
            )
            orphaned_jobs = result.scalars().all()

            for job in orphaned_jobs:
                logger.warning(f"Cleaning up orphaned job {job.id} (status: {job.status})")
                job.status = "FAILED"
                job.error_log = "Job terminated due to service restart"
                job.completed_at = datetime.utcnow()
                if job.started_at:
                    job.elapsed_seconds = int((job.completed_at - job.started_at).total_seconds())

            if orphaned_jobs:
                await db.commit()
                logger.info(f"Cleaned up {len(orphaned_jobs)} orphaned jobs")
    except Exception as e:
        logger.warning(f"Orphaned job cleanup failed: {e}")

    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on application shutdown"""
    logger.info("Shutting down application...")

    # Clear GPU memory
    try:
        from app.services.gpu_engine import GPUMonitor
        GPUMonitor.clear_gpu_memory()
        logger.info("GPU memory cleared")
    except Exception as e:
        logger.warning(f"GPU cleanup failed: {e}")

    logger.info("Application shutdown complete")

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": settings.APP_NAME,
        "version": "2.0.0",
        "status": "operational",
        "gpu_available": GPU_INFO.get("available", False),
        "gpu_name": GPU_INFO.get("name"),
        "documentation": "/docs"
    }

@app.get("/info")
async def service_info():
    """Detailed service information"""
    return {
        "service": settings.APP_NAME,
        "version": "2.0.0",
        "environment": settings.ENV,
        "gpu_info": GPU_INFO,
        "config": {
            "max_concurrent_jobs": settings.MAX_CONCURRENT_JOBS,
            "gpu_memory_threshold_gb": settings.GPU_MEMORY_THRESHOLD_GB,
            "default_max_seq_length": settings.DEFAULT_MAX_SEQ_LENGTH,
        }
    }
