"""Pydantic schemas for OpenAI-compatible fine-tuning service"""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


def _to_unix_timestamp(value: Any) -> Optional[int]:
    """Convert a datetime object or integer to a Unix timestamp integer.

    DB columns may return either a ``datetime`` instance or a plain ``int``
    (epoch seconds) depending on the driver / mapping layer.  This helper
    handles both cases safely.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return int(value.timestamp())
    # Already an int/float epoch value
    return int(value)

class JobStatus(str, Enum):
    """Fine-tuning job status"""
    VALIDATING_FILES = "validating_files"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ResourceType(str, Enum):
    """Resource types for fine-tuning"""
    NVIDIA = "nvidia"

class EventLevel(str, Enum):
    """Event log levels"""
    INFO = "info"
    WARN = "warn"
    ERROR = "error"

# Model schemas
class ModelObject(BaseModel):
    """Model object response"""
    id: str
    object: str = "model"
    created: int
    owned_by: str

class ModelListResponse(BaseModel):
    """Model list response"""
    object: str = "list"
    data: List[ModelObject]

# Hyperparameter schemas
class Hyperparameters(BaseModel):
    """Fine-tuning hyperparameters (OpenAI compatible)"""
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    batch_size: Optional[int] = Field(None, ge=1, le=256)
    learning_rate_multiplier: Optional[float] = Field(None, gt=0, le=10)
    n_epochs: Optional[int] = Field(None, ge=1, le=50)
    prompt_loss_weight: Optional[float] = Field(None, ge=0, le=1)
    compute_classification_metrics: Optional[bool] = None
    classification_n_classes: Optional[int] = Field(None, ge=2)
    classification_positive_class: Optional[str] = None
    classification_betas: Optional[List[float]] = None

# Fine-tuning job schemas
class CreateFineTuningJobRequest(BaseModel):
    """Create fine-tuning job request (OpenAI compatible)"""
    model: str = Field(..., min_length=1)
    training_file: str = Field(..., pattern=r"^file-[a-zA-Z0-9_-]+$")
    hyperparameters: Optional[Hyperparameters] = None
    suffix: Optional[str] = Field(None, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    validation_file: Optional[str] = Field(None, pattern=r"^file-[a-zA-Z0-9_-]+$")
    seed: Optional[int] = Field(None, ge=0, le=2147483647)
    resource_type: Optional[str] = None

class FineTuningJobError(BaseModel):
    """Fine-tuning job error details"""
    code: str
    message: str
    param: Optional[str] = None

class FineTuningJob(BaseModel):
    """Fine-tuning job response (OpenAI compatible)"""
    model_config = ConfigDict(use_enum_values=True)

    id: str
    object: str = "fine_tuning.job"
    created_at: int
    finished_at: Optional[int] = None
    fine_tuned_model: Optional[str] = None
    hyperparameters: Dict[str, Any] = {}
    model: str
    organization_id: Optional[str] = None
    result_files: List[str] = []
    seed: Optional[int] = None
    status: str
    trained_tokens: Optional[int] = None
    training_file: str
    validation_file: Optional[str] = None
    estimated_finish: Optional[int] = None
    error: Optional[FineTuningJobError] = None

    @classmethod
    def from_db_row(
        cls,
        row: Dict[str, Any],
        requesting_user_id: str,
        include_sensitive: bool = True
    ) -> "FineTuningJob":
        """
        Create FineTuningJob from database row with field-level authorization

        Args:
            row: Database row as dict
            requesting_user_id: User ID making the request
            include_sensitive: Whether to include sensitive fields (for owner only)
        """
        job_owner_id = str(row.get("user_id", ""))
        is_owner = (job_owner_id == requesting_user_id)

        # Parse hyperparameters
        hyperparams = row.get("hyperparameters", {})
        if isinstance(hyperparams, str):
            try:
                hyperparams = json.loads(hyperparams)
            except:
                hyperparams = {}

        # Base fields (always visible)
        job_data = {
            "id": row["id"],
            "object": "fine_tuning.job",
            "created_at": _to_unix_timestamp(row.get("created_at")) or 0,
            "status": row["status"],
            "model": row["model"],
        }

        # Owner-visible or explicitly included sensitive fields
        if is_owner or include_sensitive:
            job_data.update({
                "hyperparameters": hyperparams,
                "training_file": row.get("training_file", ""),
                "validation_file": row.get("validation_file"),
                "fine_tuned_model": row.get("fine_tuned_model"),
                "finished_at": _to_unix_timestamp(row.get("finished_at")),
                "trained_tokens": row.get("trained_tokens"),
                "estimated_finish": row.get("estimated_finish"),
                "result_files": (json.loads(row["result_files"]) if isinstance(row.get("result_files"), str) else row.get("result_files")) or [],
                "seed": row.get("seed"),
            })

            # Add error if present
            if row.get("error_code"):
                job_data["error"] = {
                    "code": row["error_code"],
                    "message": row.get("error_message", ""),
                    "param": row.get("error_param")
                }

        return cls(**job_data)

class FineTuningJobListResponse(BaseModel):
    """Fine-tuning job list response"""
    object: str = "list"
    data: List[FineTuningJob]
    has_more: bool = False

# Job event schemas
class FineTuningJobEvent(BaseModel):
    """Fine-tuning job event"""
    id: str
    object: str = "fine_tuning.job.event"
    created_at: int
    level: EventLevel
    message: str
    data: Dict[str, Any] = {}

class FineTuningJobEventListResponse(BaseModel):
    """Fine-tuning job event list response"""
    object: str = "list"
    data: List[FineTuningJobEvent]

# Checkpoint schemas
class CheckpointMetrics(BaseModel):
    """Training checkpoint metrics"""
    step: int
    train_loss: Optional[float] = None
    train_accuracy: Optional[float] = None
    valid_loss: Optional[float] = None
    valid_accuracy: Optional[float] = None
    learning_rate: Optional[float] = None
    epoch: Optional[float] = None

class JobCheckpoint(BaseModel):
    """Job checkpoint information"""
    id: str
    job_id: str
    step_number: int
    metrics: CheckpointMetrics
    checkpoint_path: Optional[str] = None
    created_at: datetime

# Resource usage schemas
class ResourceUsage(BaseModel):
    """Resource usage tracking"""
    id: str
    job_id: str
    resource_type: ResourceType
    resource_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    cpu_hours: Optional[float] = None
    memory_gb_hours: Optional[float] = None
    gpu_hours: Optional[float] = None
    cost_usd: Optional[float] = None

# API response schemas
class DeleteResponse(BaseModel):
    """Delete operation response"""
    deleted: bool

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    version: Optional[str] = None
    database: Optional[str] = None

class ErrorResponse(BaseModel):
    """Error response"""
    error: Dict[str, Any]

    @classmethod
    def from_exception(cls, error_type: str, message: str, code: Optional[str] = None, param: Optional[str] = None):
        """Create error response from exception"""
        error_data = {
            "type": error_type,
            "message": message
        }
        if code:
            error_data["code"] = code
        if param:
            error_data["param"] = param

        return cls(error=error_data)

# Configuration schemas
class DatabaseConfig(BaseModel):
    """Database configuration"""
    url: str
    pool_size: int = 20
    max_overflow: int = 0
    pool_timeout: int = 30

class ServiceConfig(BaseModel):
    """Service configuration"""
    database: DatabaseConfig
    log_level: str = "INFO"
    debug: bool = False

# Resource adapter schemas
class ResourceAdapterConfig(BaseModel):
    """Resource adapter configuration"""
    type: ResourceType
    config: Dict[str, Any] = {}

class JobSubmissionRequest(BaseModel):
    """Job submission request to resource adapter"""
    job_id: str
    user_id: str
    model: str
    training_file: str  # OpenAI standard: file ID
    validation_file: Optional[str] = None
    hyperparameters: Dict[str, Any] = {}
    resource_config: Dict[str, Any] = {}  # Backend-specific config (user_uuid, username, etc.)
    user_token: Optional[str] = None  # Keycloak token for backend API authentication

class JobSubmissionResponse(BaseModel):
    """Job submission response from resource adapter"""
    success: bool
    resource_job_id: Optional[str] = None
    error_message: Optional[str] = None
    estimated_duration: Optional[int] = None  # seconds

class JobStatusRequest(BaseModel):
    """Job status request to resource adapter"""
    job_id: str
    resource_job_id: str

class JobStatusResponse(BaseModel):
    """Job status response from resource adapter"""
    status: JobStatus
    progress: Optional[float] = None  # 0.0 to 1.0
    trained_tokens: Optional[int] = None
    progress_percent: Optional[float] = None  # 0.0 to 100.0 (raw engine value)
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    current_phase: Optional[str] = None   # e.g. "Training – step 10/200 | loss: 0.12"
    training_loss: Optional[float] = None  # latest training loss from engine
    elapsed_seconds: Optional[int] = None  # wall-clock training time
    error_message: Optional[str] = None
    fine_tuned_model: Optional[str] = None
    result_files: Optional[List[str]] = []
    finished_at: Optional[int] = None  # Unix timestamp
    estimated_finish: Optional[int] = None  # Unix timestamp
    checkpoints: List[CheckpointMetrics] = []
    logs: List[str] = []