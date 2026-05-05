"""
Fine-tuning job endpoints - Create, list, retrieve, cancel jobs
"""

import json
import httpx
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..database import db_manager
from ..auth import get_current_user
from ..middleware import limiter
from ..observability import get_logger, track_job_created, track_job_cancelled
from ..errors import (
    InvalidRequestError, ResourceNotFoundError, ServerError,
    PermissionError as ForbiddenError,
    create_error_response
)
from ..validators.training_data_validator import TrainingDataValidator, SecurityError as TrainingSecurityError
from ..schemas import (
    CreateFineTuningJobRequest, FineTuningJob, FineTuningJobListResponse,
    ResourceType, JobSubmissionRequest, JobStatusRequest
)
from ..adapters.base import ResourceAdapterFactory
from ..config import get_settings

logger = get_logger(__name__)
router = APIRouter(prefix="/v1/fine_tuning", tags=["Fine-tuning"])
security = HTTPBearer()
settings = get_settings()


def _build_adapter_config(resource_type: ResourceType, current_user: Dict[str, Any]) -> Dict[str, Any]:
    """Build backend adapter configuration (backend auth is separate from user auth)."""
    user_id = current_user["user_id"]
    adapter_config: Dict[str, Any] = {
        "user_id": str(user_id),
        "user_uuid": str(user_id),
        "username": current_user.get("username", str(user_id)[:8])
    }

    if resource_type == ResourceType.NVIDIA:
        adapter_config.update({
            "nvidia_api_url": settings.nvidia.api_url,
            "api_timeout": settings.nvidia.api_timeout,
            "max_concurrent_jobs": settings.nvidia.max_jobs,
            "backend_auth_config": {
                "type": "oauth2_client_credentials",
                "token_url": settings.nvidia.keycloak_token_url,
                "client_id": settings.nvidia.keycloak_client_id,
                "client_secret": settings.nvidia.keycloak_client_secret,
                "verify_ssl": settings.nvidia.keycloak_verify_ssl,
                "refresh_buffer_seconds": 300,
                "timeout": 30.0
            }
        })

    return adapter_config


def _dump_hyperparameters(hyperparameters: Optional[Any]) -> Dict[str, Any]:
    """Normalize hyperparameters to a plain dict."""
    if not hyperparameters:
        return {}
    if hasattr(hyperparameters, "model_dump"):
        return hyperparameters.model_dump()
    if hasattr(hyperparameters, "dict"):
        return hyperparameters.dict()
    return dict(hyperparameters)


def _parse_hyperparameters(value: Optional[Any]) -> Dict[str, Any]:
    """Parse stored hyperparameters into a dict."""
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return dict(value)


@router.post("/jobs", response_model=FineTuningJob)
@limiter.limit(f"{settings.rate_limit.job_create}/minute")
async def create_fine_tuning_job(
    request: Request,
    job_request: CreateFineTuningJobRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create a fine-tuning job

    Submit a fine-tuning job to train a custom model. The job will be queued
    and processed by the training backend.

    **Required Parameters:**
    - `model`: Base model to fine-tune (e.g., "meta-llama/Llama-3.2-3B-Instruct")
    - `training_file`: File ID of training data (JSONL format)

    **Optional Parameters:**
    - `hyperparameters`: Training hyperparameters (epochs, batch size, learning rate)
    - `validation_file`: File ID for validation data
    - `suffix`: Custom suffix for the fine-tuned model name
    """
    try:
        user_id = current_user["user_id"]
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        resource_type_str = job_request.resource_type or "nvidia"

        # Security: Check concurrent jobs limit (Resource consumption control - OWASP API4)
        active_jobs_count = await db_manager.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM fine_tuning_jobs
            WHERE user_id = $1 AND status IN ('validating_files', 'queued', 'running')
            """,
            user_id,
            timeout=30
        )

        max_concurrent_jobs = getattr(settings, 'max_concurrent_jobs_per_user', 3)
        if active_jobs_count and active_jobs_count.get("count", 0) >= max_concurrent_jobs:
            logger.warning(
                "User exceeded concurrent jobs limit",
                extra={
                    "user_id": user_id,
                    "active_jobs": active_jobs_count.get("count"),
                    "max_allowed": max_concurrent_jobs,
                    "correlation_id": correlation_id
                }
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": {
                        "message": f"Maximum {max_concurrent_jobs} concurrent jobs allowed. Please wait for existing jobs to complete.",
                        "type": "rate_limit_error",
                        "code": "concurrent_jobs_limit_exceeded"
                    }
                }
            )

        logger.info(
            "Job creation started",
            extra={
                "user_id": user_id,
                "model": job_request.model,
                "training_file": job_request.training_file,
                "resource_type": resource_type_str,
                "correlation_id": correlation_id
            }
        )

        # Validate resource type
        try:
            resource_type = ResourceType(resource_type_str)
        except ValueError:
            available = ResourceAdapterFactory.get_available_resources()
            raise InvalidRequestError(
                f"Invalid resource type '{resource_type_str}'. Available: {', '.join([r.value for r in available])}",
                code="invalid_resource_type"
            )

        # Check resource availability
        available_resources = ResourceAdapterFactory.get_available_resources()
        if resource_type not in available_resources:
            raise InvalidRequestError(
                f"Resource not available. Available: {', '.join([r.value for r in available_resources])}",
                code="resource_unavailable"
            )

        # Generate job ID
        job_id = f"ftjob-{uuid4().hex[:16]}"
        logger.info(f"Creating job {job_id} for user {user_id} on {resource_type.value}")

        # Verify training file from dataprep (optional)
        dataprep_token = credentials.credentials
        filename = f"{job_request.training_file}.jsonl"

        if settings.dataprep.api_url:
            try:
                async with httpx.AsyncClient(
                    timeout=settings.dataprep.timeout,
                    verify=settings.dataprep.verify_ssl
                ) as client:
                    # Step 1: Fetch file metadata
                    file_response = await client.get(
                        f"{settings.dataprep.api_url}/v1/files/{job_request.training_file}",
                        headers={"Authorization": f"Bearer {dataprep_token}"}
                    )

                    if file_response.status_code == 200:
                        file_data = file_response.json()
                        filename = file_data.get("filename", filename)

                        if not filename.endswith(".jsonl"):
                            raise InvalidRequestError(
                                "Training file must be in JSONL format",
                                code="invalid_training_file"
                            )

                    # Step 2: Fetch file content and validate for security threats
                    content_response = await client.get(
                        f"{settings.dataprep.api_url}/v1/files/{job_request.training_file}/content",
                        headers={"Authorization": f"Bearer {dataprep_token}"}
                    )

                    if content_response.status_code == 200:
                        raw_content = content_response.text
                        validator = TrainingDataValidator()
                        try:
                            validation_result = validator.validate_jsonl_content(raw_content)
                            logger.info(
                                "Training data security validation passed",
                                extra={
                                    "user_id": user_id,
                                    "training_file": job_request.training_file,
                                    "item_count": validation_result.get("item_count"),
                                    "warnings": validation_result.get("warnings"),
                                    "correlation_id": correlation_id,
                                }
                            )
                        except TrainingSecurityError as sec_err:
                            logger.error(
                                "Malicious pattern detected in training data",
                                extra={
                                    "user_id": user_id,
                                    "training_file": job_request.training_file,
                                    "error": str(sec_err),
                                    "correlation_id": correlation_id,
                                }
                            )
                            raise InvalidRequestError(
                                f"Training data failed security scan: {sec_err}",
                                code="training_data_security_violation",
                                param="training_file",
                            )
                        except ValueError as val_err:
                            logger.warning(
                                "Training data format/content validation failed",
                                extra={
                                    "user_id": user_id,
                                    "training_file": job_request.training_file,
                                    "error": str(val_err),
                                    "correlation_id": correlation_id,
                                }
                            )
                            raise InvalidRequestError(
                                str(val_err),
                                code="invalid_training_data",
                                param="training_file",
                            )
                    else:
                        logger.warning(
                            "Could not fetch training file content for validation — continuing",
                            extra={
                                "user_id": user_id,
                                "training_file": job_request.training_file,
                                "status_code": content_response.status_code,
                            }
                        )
            except (InvalidRequestError,):
                raise
            except httpx.TimeoutException:
                # Dataprep (security/data-validation) service is unreachable.
                # Do NOT silently continue – reject the job so untrusted data
                # is never forwarded to the training backend.
                logger.error("Dataprep service timeout during security validation")
                raise HTTPException(
                    status_code=503,
                    detail="Training data security validation service is temporarily unavailable. "
                           "Please retry your request."
                )
            except httpx.HTTPError as e:
                # Any HTTP-level error from the dataprep service is treated as a
                # hard failure so the job is not created with unvalidated data.
                logger.error(f"Dataprep service error during security validation: {e}")
                raise HTTPException(
                    status_code=503,
                    detail="Training data security validation service returned an error. "
                           "Please retry your request."
                )

        # Validate model against base_models table (using allowlist approach)
        model_row = await db_manager.fetch_one(
            """
            SELECT id
            FROM base_models
            WHERE id = $1 AND is_active = true
            """,
            job_request.model,
            timeout=30
        )
        if not model_row:
            logger.warning(
                "Attempt to use unavailable model",
                extra={
                    "user_id": user_id,
                    "model": job_request.model,
                    "correlation_id": correlation_id
                }
            )
            raise InvalidRequestError(
                f"Model '{job_request.model}' is not available",
                code="model_not_available",
                param="model"
            )

        # Convert hyperparameters
        hyperparams_dict = _dump_hyperparameters(job_request.hyperparameters)

        # Prepare adapter config
        adapter_config = _build_adapter_config(resource_type, current_user)

        # Create job submission request
        submission_request = JobSubmissionRequest(
            job_id=job_id,
            user_id=str(user_id),
            model=job_request.model,
            training_file=job_request.training_file,
            validation_file=job_request.validation_file,
            hyperparameters=hyperparams_dict,
            resource_config=adapter_config,
            user_token=credentials.credentials
        )

        # Submit job via adapter
        adapter = ResourceAdapterFactory.create_adapter(resource_type, config=adapter_config)
        submission_response = await adapter.submit_job(submission_request)

        if not submission_response.success:
            error_msg = submission_response.error_message or "Unknown error"
            logger.error(f"Job submission failed: {error_msg}")

            # Parse error and return appropriate response
            error_lower = error_msg.lower()

            if "429" in error_msg or "service busy" in error_lower:
                return create_error_response(
                    "Service at capacity. Please try again later.",
                    "resource_exhausted",
                    "rate_limit_exceeded",
                    429
                )
            elif "401" in error_msg or "403" in error_msg:
                return create_error_response(
                    "Authentication failed. Check credentials.",
                    "authentication_error",
                    "invalid_credentials",
                    401
                )
            elif "404" in error_msg:
                return create_error_response(
                    "Resource not found. Verify training file exists.",
                    "invalid_request_error",
                    "resource_not_found",
                    404
                )
            elif any(code in error_msg for code in ["500", "502", "503", "504"]):
                return create_error_response(
                    "Service temporarily unavailable.",
                    "server_error",
                    "service_unavailable",
                    503
                )
            else:
                user_friendly_msg = "Unable to start fine-tuning job"
                if "file" in error_lower:
                    user_friendly_msg = "Unable to access training file"
                elif "model" in error_lower:
                    user_friendly_msg = "Model not available"

                return create_error_response(
                    user_friendly_msg,
                    "api_error",
                    "backend_error",
                    502
                )

        resource_job_id = submission_response.resource_job_id
        logger.info(
            "Job submitted to backend successfully",
            extra={
                "job_id": job_id,
                "resource_job_id": resource_job_id,
                "user_id": user_id,
                "correlation_id": correlation_id
            }
        )

        # Store job in database
        created_at = int(datetime.utcnow().timestamp())
        status_value = "validating_files"

        await db_manager.execute("""
            INSERT INTO fine_tuning_jobs
            (id, model, training_file, validation_file, hyperparameters,
             resource_type, resource_job_id, user_id, created_at, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """, job_id, job_request.model, job_request.training_file,
            job_request.validation_file, json.dumps(hyperparams_dict),
            resource_type.value, resource_job_id, user_id, created_at, status_value,
            timeout=30)

        logger.info(
            "Job created successfully",
            extra={
                "job_id": job_id,
                "user_id": user_id,
                "status": status_value,
                "correlation_id": correlation_id
            }
        )

        # Track job creation for metrics
        track_job_created(current_user.get("preferred_username") or current_user.get("sub") or str(user_id))

        # Return OpenAI-compatible response
        return {
            "id": job_id,
            "object": "fine_tuning.job",
            "model": job_request.model,
            "created_at": created_at,
            "finished_at": None,
            "fine_tuned_model": None,
            "organization_id": None,
            "result_files": [],
            "status": status_value,
            "validation_file": job_request.validation_file,
            "training_file": job_request.training_file,
            "hyperparameters": hyperparams_dict,
            "trained_tokens": None,
            "error": None
        }

    except (InvalidRequestError, ResourceNotFoundError):
        raise
    except Exception as e:
        logger.error(f"Job creation failed: {e}", exc_info=True)
        raise ServerError("Unable to create fine-tuning job. Please try again or contact support if the issue persists.")


@router.get("/jobs", response_model=FineTuningJobListResponse)
@limiter.limit(f"{settings.rate_limit.job_read}/minute")
async def list_fine_tuning_jobs(
    request: Request,
    limit: int = 20,
    after: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List fine-tuning jobs for the current user

    Returns a paginated list of fine-tuning jobs owned by the authenticated user.
    Field-level authorization ensures users only see their own job details.
    """
    try:
        user_id = current_user["user_id"]
        correlation_id = getattr(request.state, "correlation_id", "unknown")

        logger.info(
            "Listing jobs for user",
            extra={
                "user_id": user_id,
                "limit": limit,
                "correlation_id": correlation_id
            }
        )

        rows = await db_manager.fetch_all("""
            SELECT id, model, training_file, validation_file, hyperparameters,
                   status, created_at, updated_at, finished_at, fine_tuned_model,
                   trained_tokens, error_message, error_code, error_param, result_files, user_id
            FROM fine_tuning_jobs
            WHERE user_id = $1
            ORDER BY created_at DESC LIMIT $2
        """, user_id, limit, timeout=30)

        # Use field-level authorization from schema
        jobs = []
        for row in rows:
            job = FineTuningJob.from_db_row(
                row,
                requesting_user_id=str(user_id),
                include_sensitive=True  # User is owner
            )
            jobs.append(job)

        return {
            "object": "list",
            "data": jobs,
            "has_more": False
        }
    except Exception as e:
        logger.error(
            "List jobs failed",
            extra={
                "user_id": current_user.get("user_id"),
                "error": str(e),
                "correlation_id": getattr(request.state, "correlation_id", "unknown")
            },
            exc_info=True
        )
        raise ServerError("Unable to retrieve jobs list. Please try again later.")


@router.get("/jobs/{job_id}", response_model=FineTuningJob)
@limiter.limit(f"{settings.rate_limit.job_read}/minute")
async def get_fine_tuning_job(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get fine-tuning job details with real-time status from backend

    Fetches the latest job status from the training backend and updates the local cache.
    Field-level authorization ensures users can only access their own job details.
    """
    try:
        user_id = current_user["user_id"]
        correlation_id = getattr(request.state, "correlation_id", "unknown")

        logger.info(
            "Fetching job details",
            extra={
                "job_id": job_id,
                "user_id": user_id,
                "correlation_id": correlation_id
            }
        )

        # Check if job exists
        row = await db_manager.fetch_one("""
            SELECT id, model, training_file, validation_file, hyperparameters,
                   status, created_at, updated_at, finished_at, fine_tuned_model,
                   trained_tokens, error_message, resource_type, resource_job_id, user_id
            FROM fine_tuning_jobs
            WHERE id = $1
        """, job_id, timeout=30)

        if not row:
            logger.warning(
                "Job not found",
                extra={
                    "job_id": job_id,
                    "user_id": user_id,
                    "correlation_id": correlation_id
                }
            )
            raise ResourceNotFoundError("fine-tuning job", job_id)

        # Field-level authorization
        job_owner_id = str(row.get("user_id", ""))
        is_owner = (job_owner_id == str(user_id))

        if not is_owner:
            logger.warning(
                "Unauthorized job access attempt — returning 403",
                extra={
                    "job_id": job_id,
                    "requesting_user_id": user_id,
                    "owner_user_id": job_owner_id,
                    "correlation_id": correlation_id,
                }
            )
            raise ForbiddenError("You do not have permission to access this fine-tuning job")

        resource_type = ResourceType(row['resource_type'])
        resource_job_id = row['resource_job_id']
        job_data = None

        # Fetch real-time status from backend
        if resource_job_id:
            try:
                adapter_config = _build_adapter_config(resource_type, current_user)
                adapter_config["api_timeout"] = 8.0

                adapter = ResourceAdapterFactory.create_adapter(resource_type, config=adapter_config)
                status_request = JobStatusRequest(
                    job_id=job_id,
                    resource_job_id=resource_job_id
                )

                status_response = await adapter.get_job_status(status_request)

                if status_response:
                    job_data = {
                        "id": row['id'],
                        "object": "fine_tuning.job",
                        "model": row['model'],
                        "created_at": row['created_at'],
                        "finished_at": status_response.finished_at,
                        "fine_tuned_model": status_response.fine_tuned_model,
                        "status": status_response.status.value,
                        "trained_tokens": status_response.trained_tokens,
                        "training_file": row['training_file'],
                        "validation_file": row['validation_file'],
                        "hyperparameters": _parse_hyperparameters(row['hyperparameters']),
                        "error": {"message": status_response.error_message} if status_response.error_message else None,
                        "result_files": status_response.result_files or [],
                        "estimated_finish": status_response.estimated_finish
                    }
                    logger.info(f"Fetched job {job_id} from backend, status: {status_response.status.value}")

            except Exception as e:
                logger.warning(f"Error fetching from backend for job {job_id}: {e}")

        # Fallback to database cache
        if not job_data:
            job_data = {
                "id": row['id'],
                "object": "fine_tuning.job",
                "model": row['model'],
                "created_at": row['created_at'],
                "finished_at": row['finished_at'],
                "fine_tuned_model": row['fine_tuned_model'],
                "status": row['status'],
                "trained_tokens": row['trained_tokens'],
                "training_file": row['training_file'],
                "validation_file": row['validation_file'],
                "hyperparameters": _parse_hyperparameters(row['hyperparameters']),
                "error": {"message": row['error_message']} if row['error_message'] else None,
                "result_files": [row['fine_tuned_model']] if row['fine_tuned_model'] else []
            }
            logger.info(f"Returned cached data for job {job_id}")

        return job_data

    except (ResourceNotFoundError, ForbiddenError):
        raise
    except Exception as e:
        logger.error(f"Get job failed: {e}", exc_info=True)
        raise ServerError("Unable to retrieve job details. Please try again later.")


@router.post("/jobs/{job_id}/cancel")
@limiter.limit(f"{settings.rate_limit.job_cancel}/minute")
async def cancel_fine_tuning_job(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Cancel a fine-tuning job

    Attempts to cancel a queued or running fine-tuning job.
    """
    try:
        # Check if job exists (without user filter — we handle 403 explicitly)
        row = await db_manager.fetch_one("""
            SELECT id, status, user_id, resource_type, resource_job_id
            FROM fine_tuning_jobs
            WHERE id = $1
        """, job_id)

        if not row:
            raise ResourceNotFoundError("fine-tuning job", job_id)

        # Authorization: only the owner may cancel
        if str(row["user_id"]) != str(current_user["user_id"]):
            logger.warning(
                "Unauthorized cancel attempt — returning 403",
                extra={
                    "job_id": job_id,
                    "requesting_user_id": current_user["user_id"],
                    "owner_user_id": row["user_id"],
                }
            )
            raise ForbiddenError("You do not have permission to cancel this fine-tuning job")

        # Check if cancellable
        if row["status"] not in ["queued", "running", "validating_files"]:
            status_messages = {
                "succeeded": "Job has already completed successfully.",
                "failed": "Job has already failed.",
                "cancelled": "Job has already been cancelled."
            }
            msg = status_messages.get(row["status"], f"Job is in '{row['status']}' state.")
            raise InvalidRequestError(f"Cannot cancel job. {msg}", code="job_not_cancellable")

        # Cancel via adapter
        resource_type = ResourceType(row["resource_type"])
        resource_job_id = row["resource_job_id"]

        adapter_config = _build_adapter_config(resource_type, current_user)

        adapter = ResourceAdapterFactory.create_adapter(resource_type, config=adapter_config)
        auth_token = current_user.get("token")
        success = await adapter.cancel_job(job_id, resource_job_id, auth_token)

        if not success:
            raise ServerError("Unable to cancel job at this time")

        # Update database
        await db_manager.execute("""
            UPDATE fine_tuning_jobs
            SET status = 'cancelled',
                updated_at = $1,
                finished_at = $1
            WHERE id = $2
        """, int(datetime.utcnow().timestamp()), job_id)

        logger.info(f"Cancelled job {job_id}")

        # Track job cancellation for metrics
        track_job_cancelled(current_user.get("preferred_username") or current_user.get("sub") or current_user.get("user_id", "unknown"))

        return {
            "id": job_id,
            "object": "fine_tuning.job",
            "status": "cancelled",
            "cancelled_at": int(datetime.utcnow().timestamp())
        }

    except (InvalidRequestError, ResourceNotFoundError, ForbiddenError):
        raise
    except Exception as e:
        logger.error(f"Cancel job failed: {e}", exc_info=True)
        raise ServerError("Unable to cancel job. Please try again or contact support.")


@router.get("/jobs/{job_id}/events")
@limiter.limit(f"{settings.rate_limit.job_events}/minute")
async def list_fine_tuning_events(
    request: Request,
    job_id: str,
    after: Optional[str] = None,
    limit: int = 20,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List fine-tuning job events

    Returns a list of events for the specified fine-tuning job, including
    status changes, progress updates, and error messages.
    """
    try:
        # Check if job exists (without user filter — we handle 403 explicitly)
        row = await db_manager.fetch_one("""
            SELECT id, user_id, resource_type, resource_job_id
            FROM fine_tuning_jobs
            WHERE id = $1
        """, job_id)

        if not row:
            raise ResourceNotFoundError("fine-tuning job", job_id)

        # Authorization: only the owner may view events
        if str(row["user_id"]) != str(current_user["user_id"]):
            logger.warning(
                "Unauthorized events access attempt — returning 403",
                extra={
                    "job_id": job_id,
                    "requesting_user_id": current_user["user_id"],
                    "owner_user_id": row["user_id"],
                }
            )
            raise ForbiddenError("You do not have permission to view events for this fine-tuning job")

        # Get events from backend via adapter
        resource_type = ResourceType(row["resource_type"])
        resource_job_id = row["resource_job_id"]

        adapter_config = _build_adapter_config(resource_type, current_user)
        adapter_config["api_timeout"] = 10.0

        adapter = ResourceAdapterFactory.create_adapter(resource_type, config=adapter_config)
        events = await adapter.get_job_events(job_id, resource_job_id, limit)

        return events

    except (ResourceNotFoundError, ForbiddenError):
        raise
    except Exception as e:
        logger.error(f"List events failed: {e}", exc_info=True)
        raise ServerError("Unable to retrieve job events. Please try again later.")


@router.get("/jobs/{job_id}/checkpoints")
@limiter.limit(f"{settings.rate_limit.job_read}/minute")
async def list_fine_tuning_checkpoints(
    request: Request,
    job_id: str,
    after: Optional[str] = None,
    limit: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List fine-tuning job checkpoints

    Returns training checkpoints for the specified job (if supported by backend).
    """
    try:
        # Check if job exists (without user filter — we handle 403 explicitly)
        row = await db_manager.fetch_one("""
            SELECT id, user_id FROM fine_tuning_jobs
            WHERE id = $1
        """, job_id)

        if not row:
            raise ResourceNotFoundError("fine-tuning job", job_id)

        # Authorization: only the owner may view checkpoints
        if str(row["user_id"]) != str(current_user["user_id"]):
            logger.warning(
                "Unauthorized checkpoints access attempt — returning 403",
                extra={
                    "job_id": job_id,
                    "requesting_user_id": current_user["user_id"],
                    "owner_user_id": row["user_id"],
                }
            )
            raise ForbiddenError("You do not have permission to view checkpoints for this fine-tuning job")

        # Checkpoints not currently supported
        return {
            "object": "list",
            "data": [],
            "has_more": False
        }

    except (ResourceNotFoundError, ForbiddenError):
        raise
    except Exception as e:
        logger.error(f"List checkpoints failed: {e}", exc_info=True)
        raise ServerError("Unable to retrieve job checkpoints. Please try again later.")
