# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from datetime import datetime
import logging
import asyncio

from app.database import get_db, AsyncSessionLocal
from app.models import TrainingJob
from app.schemas import (
    TrainingRequest, JobStatusResponse, AvailabilityResponse,
    GPUStatusResponse, JobCancelResponse
)
from app.auth import verify_access_token, get_files_api_token
from app.config import settings, GPU_INFO
from app.services import file_client, gpu_engine
from app.services.model_watermarking import watermark_model
from app.validators.training_data_validator import (
    validate_model_allowlist,
    validate_training_file,
    TrainingDataValidationError,
)
from app.middleware.model_extraction_detector import extraction_detector
from app.limiter import limiter

router = APIRouter(prefix="/finetune", tags=["Finetuning"])
logger = logging.getLogger("uvicorn")

# Store for job cancellation flags
job_cancellation_flags: dict[int, bool] = {}

# Store for active asyncio tasks so they can be properly cancelled on delete
active_training_tasks: dict[int, asyncio.Task] = {}

def update_job_progress_sync(job_id: int, progress_data: dict):
    """
    Simple progress logger - just logs, no DB update
    DB updates happen at start/end of training
    """
    logger.info(f"Job {job_id} - Step {progress_data.get('current_step')}/{progress_data.get('max_steps')} - Loss: {progress_data.get('loss', 'N/A')}")

async def background_training_task(job_id: int, request: TrainingRequest, bearer_token: str):
    """Background task to execute training with FILES API bearer token"""
    async with AsyncSessionLocal() as db:
        job = await db.get(TrainingJob, job_id)

        try:
            # Check for cancellation
            if job_cancellation_flags.get(job_id, False):
                job.status = "CANCELLED"
                job.error_log = "Job cancelled by user"
                await db.commit()
                return

            # Update status to RUNNING
            job.status = "RUNNING"
            job.started_at = datetime.utcnow()
            await db.commit()

            # --- AI/ML Security: Base model allowlist check ---
            try:
                validate_model_allowlist(request.model_name)
            except TrainingDataValidationError as e:
                # Re-raise as a plain exception so it's caught by the outer try/except
                raise ValueError(str(e))

            logger.info(f"Job {job_id}: Downloading dataset with bearer token...")
            # Run download in thread to avoid blocking - pass bearer token
            local_file = await asyncio.to_thread(
                file_client.download_dataset,
                filename=request.input_filenames[0],
                bearer_token=bearer_token
            )

            # Check for cancellation
            if job_cancellation_flags.get(job_id, False):
                job.status = "CANCELLED"
                await db.commit()
                return

            # --- AI/ML Security: Validate training data before training ---
            logger.info(f"Job {job_id}: Scanning training data for malicious content...")
            try:
                await asyncio.to_thread(validate_training_file, local_file)
            except TrainingDataValidationError as e:
                logger.error(f"Job {job_id}: Training data validation FAILED: {e}")
                raise
            logger.info(f"Job {job_id}: Training data validation passed.")

            logger.info(f"Job {job_id}: Starting training...")
            output_dir = f"{settings.MODEL_OUTPUT_DIR}/job_{job_id}"

            # Define cancellation check function
            def check_cancellation(jid: int) -> bool:
                return job_cancellation_flags.get(jid, False)

            # Execute training in a separate thread to avoid blocking the event loop
            # This allows other API calls to work while training is in progress
            # Use synchronous progress callback since it runs in a separate thread
            results = await asyncio.to_thread(
                gpu_engine.execute_finetuning,
                model_name=request.model_name,
                data_path=local_file,
                output_dir=output_dir,
                params=request.hyperparameters,
                job_id=job_id,
                progress_callback=update_job_progress_sync,  # Use sync wrapper
                cancellation_check=check_cancellation
            )

            # Check for cancellation before upload
            if job_cancellation_flags.get(job_id, False):
                job.status = "CANCELLED"
                await db.commit()
                return

            logger.info(f"Job {job_id}: Uploading model...")

            # Clean up old models before upload to save disk space
            try:
                await asyncio.to_thread(
                    file_client.cleanup_old_files,
                    settings.MODEL_OUTPUT_DIR,
                    max_age_hours=1
                )
            except Exception as cleanup_error:
                logger.warning(f"Cleanup warning: {cleanup_error}")

            # Run upload in thread to avoid blocking - pass bearer token
            file_id = await asyncio.to_thread(
                file_client.upload_model,
                folder_path=output_dir,
                model_name=request.model_name,
                bearer_token=bearer_token
            )

            # Update job with results
            job.status = "COMPLETED"
            job.output_file_id = file_id
            job.output_path = output_dir
            job.completed_at = datetime.utcnow()
            job.elapsed_seconds = results.get("elapsed_seconds")
            job.training_loss = results.get("training_loss")
            job.dataset_size = results.get("dataset_size")

            # --- AI/ML Security: Watermark the model ---
            try:
                watermark_model(
                    output_dir=output_dir,
                    job_id=job_id,
                    username=request.username,
                    model_name=request.model_name,
                )
            except Exception as wm_err:
                logger.warning(f"Job {job_id}: Watermarking failed (non-fatal): {wm_err}")

            if results.get("final_memory_gb"):
                job.gpu_memory_used_gb = results["final_memory_gb"].get("allocated_gb")
                job.gpu_utilization_percent = results["final_memory_gb"].get("utilization_percent")

            await db.commit()
            logger.info(f"Job {job_id}: Completed successfully")

        except asyncio.CancelledError:
            logger.info(f"Job {job_id}: asyncio task was cancelled")
            job.status = "CANCELLED"
            job.error_log = "Job cancelled by user"
            job.completed_at = datetime.utcnow()
            if job.started_at:
                job.elapsed_seconds = int(
                    (job.completed_at - job.started_at).total_seconds()
                )
            try:
                await db.commit()
            except Exception:
                pass
            raise  # Re-raise so asyncio marks the task as cancelled
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            job.status = "FAILED"
            job.error_log = str(e)
            job.completed_at = datetime.utcnow()
            if job.started_at:
                job.elapsed_seconds = int((job.completed_at - job.started_at).total_seconds())
            await db.commit()
        finally:
            # Clean up both stores regardless of outcome
            job_cancellation_flags.pop(job_id, None)
            active_training_tasks.pop(job_id, None)


@router.get("/gpu-status", response_model=GPUStatusResponse, dependencies=[Depends(verify_access_token)])
async def get_gpu_status():
    """Get current GPU status and memory usage"""
    memory_info = gpu_engine.GPUMonitor.get_gpu_memory_info()

    return GPUStatusResponse(
        gpu_available=GPU_INFO.get("available", False),
        gpu_name=GPU_INFO.get("name"),
        gpu_count=GPU_INFO.get("count", 0),
        total_memory_gb=memory_info.get("total_gb", 0.0),
        allocated_memory_gb=memory_info.get("allocated_gb", 0.0),
        free_memory_gb=memory_info.get("free_gb", 0.0),
        utilization_percent=memory_info.get("utilization_percent", 0.0),
        cuda_version=GPU_INFO.get("cuda_version")
    )


async def _get_service_availability(db: AsyncSession) -> AvailabilityResponse:
    """Return current service availability status without raising exceptions.

    Centralises the availability logic so that both the /availability endpoint
    and the /start endpoint share a single source of truth.
    """
    result = await db.execute(
        select(func.count(TrainingJob.id)).where(TrainingJob.status == "RUNNING")
    )
    running_jobs = result.scalar()

    if running_jobs >= settings.MAX_CONCURRENT_JOBS:
        return AvailabilityResponse(
            available=False,
            message=f"Service busy: {running_jobs}/{settings.MAX_CONCURRENT_JOBS} jobs running",
            running_jobs=running_jobs,
            max_concurrent_jobs=settings.MAX_CONCURRENT_JOBS,
        )

    if not GPU_INFO.get("available"):
        return AvailabilityResponse(
            available=False,
            message="No GPU available",
            running_jobs=running_jobs,
            max_concurrent_jobs=settings.MAX_CONCURRENT_JOBS,
        )

    memory_info = gpu_engine.GPUMonitor.get_gpu_memory_info()
    if memory_info.get("free_gb", 0) < settings.GPU_MEMORY_THRESHOLD_GB:
        return AvailabilityResponse(
            available=False,
            message=(
                f"Insufficient GPU memory: "
                f"{memory_info.get('free_gb', 0):.2f}GB available"
            ),
            running_jobs=running_jobs,
            max_concurrent_jobs=settings.MAX_CONCURRENT_JOBS,
        )

    return AvailabilityResponse(
        available=True,
        message="Service ready",
        running_jobs=running_jobs,
        max_concurrent_jobs=settings.MAX_CONCURRENT_JOBS,
    )


@router.get("/availability", response_model=AvailabilityResponse, dependencies=[Depends(verify_access_token)])
async def check_availability(db: AsyncSession = Depends(get_db)):
    """Check if the service is available to accept new jobs"""
    return await _get_service_availability(db)


@router.post("/start", status_code=202, dependencies=[Depends(verify_access_token)])
@limiter.limit("5/minute")
async def start_job(
    request: Request,
    body: TrainingRequest,
    db: AsyncSession = Depends(get_db),
    bearer_token: str = Depends(get_files_api_token),
):
    """
    Start a new fine-tuning job.

    Requires:
    - Authorization: Bearer <keycloak-token>  (Keycloak JWT for service authentication)
    - ft-api-key: <files-api-token>           (Bearer token for FILES API authentication)

    Rate limited: 5 requests per minute per IP.
    """
    # Reuse centralised availability check
    availability = await _get_service_availability(db)
    if not availability.available:
        status_code = 429 if "busy" in availability.message.lower() else 503
        raise HTTPException(status_code=status_code, detail=availability.message)

    # Create new job with optional custom job_id
    if body.job_id is not None:
        existing_job = await db.get(TrainingJob, body.job_id)
        if existing_job:
            raise HTTPException(
                status_code=400,
                detail=f"Job ID {body.job_id} already exists",
            )
        new_job = TrainingJob(
            id=body.job_id,
            username=body.username,
            model_name=body.model_name,
            input_filename=body.input_filenames[0],
            hyperparameters=body.hyperparameters,
            total_steps=body.hyperparameters.get("max_steps"),
            status="PENDING",
        )
    else:
        # Auto-generate job_id
        new_job = TrainingJob(
            username=body.username,
            model_name=body.model_name,
            input_filename=body.input_filenames[0],
            hyperparameters=body.hyperparameters,
            total_steps=body.hyperparameters.get("max_steps"),
            status="PENDING",
        )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    # Log bearer token receipt (redacted for security)
    logger.info(f"Received FILES API bearer token for job (length: {len(bearer_token)} chars)")

    # Schedule training as a proper asyncio Task so it can be cancelled later
    task = asyncio.create_task(
        background_training_task(new_job.id, body, bearer_token),
        name=f"training_job_{new_job.id}",
    )
    active_training_tasks[new_job.id] = task

    logger.info(f"Job {new_job.id} queued for user {body.username}")
    return {"job_id": new_job.id, "status": "accepted", "message": "Job queued successfully"}


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(verify_access_token),
):
    """Get status of a specific job"""
    job = await db.get(TrainingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # --- AI/ML Security: Extraction detection ---
    # Track when authenticated users retrieve completed model results.
    if job.status == "COMPLETED":
        caller = (
            token_payload.get("preferred_username")
            or token_payload.get("sub")
            or "unknown"
        )
        extraction_detector.record_access(username=caller, job_id=job_id)

    return job


@router.delete("/job/{job_id}", dependencies=[Depends(verify_access_token)])
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a job — cancels the background task if running, then removes from database"""
    job = await db.get(TrainingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status in ["RUNNING", "PENDING"]:
        # 1. Signal the training thread to stop cooperatively
        job_cancellation_flags[job_id] = True

        # 2. Cancel the asyncio Task so it stops at the next await point
        task = active_training_tasks.pop(job_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.warning(
                    f"Job {job_id}: background task did not finish cleanly within timeout"
                )
        logger.info(f"Job {job_id}: background task cancelled")

    # Remove from database
    await db.delete(job)
    await db.commit()

    # Clean up any remaining flags
    job_cancellation_flags.pop(job_id, None)

    logger.info(f"Job {job_id} deleted from database")
    return {"job_id": job_id, "message": "Job deleted successfully"}

@router.get("/history/{username}", response_model=list[JobStatusResponse], dependencies=[Depends(verify_access_token)])
async def get_history(username: str, limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get training job history for a user"""
    result = await db.execute(
        select(TrainingJob)
        .where(TrainingJob.username == username)
        .order_by(TrainingJob.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()

@router.get("/jobs", response_model=list[JobStatusResponse], dependencies=[Depends(verify_access_token)])
async def list_all_jobs(
    username: str = None,
    status: str = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List all jobs with optional username and status filters"""
    query = select(TrainingJob).order_by(TrainingJob.created_at.desc()).limit(limit)

    if username:
        query = query.where(TrainingJob.username == username)

    if status:
        query = query.where(TrainingJob.status == status.upper())

    result = await db.execute(query)
    return result.scalars().all()
