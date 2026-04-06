"""
Health and monitoring endpoints
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..database import db_manager
from ..config import get_settings
from ..middleware import limiter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Monitoring"])
settings = get_settings()


@router.get("/api/health")
@limiter.limit(f"{settings.rate_limit.health}/minute")
async def health_check(request: Request):
    """
    Health check endpoint for load balancers and monitoring

    Returns service health status and basic diagnostics.
    """
    try:
        # Check database connectivity
        async with db_manager.acquire() as conn:
            await conn.fetchval("SELECT 1")

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": settings.api.version,
            "environment": settings.environment.value,
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": "Service unavailable"
            }
        )


@router.get("/api/readiness")
async def readiness_check():
    """
    Readiness check for Kubernetes

    Returns 200 if service is ready to accept traffic.
    """
    try:
        async with db_manager.acquire() as conn:
            await conn.fetchval("SELECT 1")

        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": str(e)}
        )


@router.get("/api/liveness")
async def liveness_check():
    """
    Liveness check for Kubernetes

    Returns 200 if service is alive (doesn't check dependencies).
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}
