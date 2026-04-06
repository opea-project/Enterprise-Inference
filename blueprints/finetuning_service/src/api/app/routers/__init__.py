"""
API Router modules for organizing endpoints
"""

from .health import router as health_router
from .models import router as models_router
from .jobs import router as jobs_router

__all__ = ["health_router", "models_router", "jobs_router"]
