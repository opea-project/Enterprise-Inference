"""
Resource Adapter Base Classes and Factory Pattern
Language-agnostic interface for different compute resources
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import asyncpg

from ..schemas import (
    JobSubmissionRequest,
    JobSubmissionResponse,
    JobStatusRequest,
    JobStatusResponse,
    ResourceType
)

class ResourceAdapter(ABC):
    """Abstract base class for resource adapters"""

    def __init__(self, db_pool: asyncpg.Pool, config: Dict[str, Any] = None):
        self.db_pool = db_pool
        self.config = config or {}

    @abstractmethod
    async def submit_job(self, request: JobSubmissionRequest) -> JobSubmissionResponse:
        """Submit a fine-tuning job to the resource"""
        pass

    @abstractmethod
    async def get_job_status(self, request: JobStatusRequest) -> JobStatusResponse:
        """Get the status of a submitted job"""
        pass

    @abstractmethod
    async def cancel_job(self, job_id: str, resource_job_id: str, auth_token: str = None) -> bool:
        """Cancel a running job"""
        pass

    @abstractmethod
    async def get_job_logs(self, job_id: str, resource_job_id: str, auth_token: str = None) -> List[str]:
        """Get job execution logs"""
        pass

    @abstractmethod
    async def list_jobs(self, username: str = None, status: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List jobs from backend"""
        pass

    @abstractmethod
    async def get_job_events(self, job_id: str, resource_job_id: str, limit: int = 20) -> Dict[str, Any]:
        """Get job events in OpenAI format"""
        pass

    @abstractmethod
    async def cleanup_job(self, job_id: str, resource_job_id: str) -> bool:
        """Clean up job resources"""
        pass

class ResourceAdapterFactory:
    """Factory for creating resource adapters"""

    _adapters: Dict[ResourceType, type] = {}
    _db_pool: Optional[asyncpg.Pool] = None

    @classmethod
    def initialize(cls, db_pool: asyncpg.Pool):
        """Initialize factory with database connection"""
        cls._db_pool = db_pool

    @classmethod
    def register_adapter(cls, resource_type: ResourceType, adapter_class: type):
        """Register a resource adapter class"""
        cls._adapters[resource_type] = adapter_class

    @classmethod
    def create_adapter(cls, resource_type: ResourceType, config: Dict[str, Any] = None) -> ResourceAdapter:
        """Create a resource adapter instance"""
        # Only Nvidia is supported currently
        if resource_type != ResourceType.NVIDIA:
            raise ValueError(f"Only Nvidia resource type is currently supported. Requested: {resource_type}")

        if resource_type not in cls._adapters:
            raise ValueError(f"No adapter registered for resource type: {resource_type}")

        if cls._db_pool is None:
            raise RuntimeError("Factory not initialized. Call initialize() first.")

        adapter_class = cls._adapters[resource_type]
        return adapter_class(cls._db_pool, config)

    @classmethod
    def get_available_resources(cls) -> List[ResourceType]:
        """Get list of available resource types"""
        # Only Nvidia is currently supported
        return [ResourceType.NVIDIA]

# Auto-import and register all adapter implementations
def _register_adapters():
    """Auto-register all available adapters"""
    from .resources.nvidia_adapter import NvidiaAdapter

    ResourceAdapterFactory.register_adapter(ResourceType.NVIDIA, NvidiaAdapter)

# Register adapters on module import
_register_adapters()