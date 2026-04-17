import logging
from typing import List, Dict, Any, Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException
from celery.result import AsyncResult

from core.handlers.auth_handler import get_current_user_id
from core.celery.celery_config import celery_app
from core.schemas.celery_schemas import (
    JobListResponse,
    JobWithStatus,
    JobStatusResponse,
    PrepareDataResponse,
)
from core.utils.job_metadata import store_job_metadata, get_jobs_by_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/dataprep", tags=["dataprep"])

# Maximum number of file IDs accepted per job submission
MAX_FILE_IDS_PER_JOB: int = 50


def _resolve_chord_status(
    task_result: AsyncResult,
) -> Tuple[str, Optional[Dict], Optional[str]]:
    """
    Resolve the status, result payload, and error string for a parent Celery
    task that may wrap a chord workflow.

    Returns a (status, result, error) tuple compatible with the existing
    JobStatusResponse / JobListResponse schemas.
    """
    status = task_result.status
    result: Optional[Dict] = None
    error: Optional[str] = None

    if not task_result.ready():
        return status, result, error

    if not task_result.successful():
        error = str(task_result.info)
        return status, result, error

    result = task_result.result

    # If the parent task delegated work to a chord, follow the chord
    if not (isinstance(result, dict) and "chord_id" in result):
        return status, result, error

    chord_id = result["chord_id"]
    chord_result = AsyncResult(chord_id, app=celery_app)
    status = chord_result.status

    if chord_result.ready():
        if chord_result.successful():
            result = chord_result.result
            # Business-logic failures are encoded in the result payload
            if isinstance(result, dict) and result.get("status") == "failed":
                status = "FAILURE"
                error = result.get("message", "Processing failed")
        else:
            result = None
            error = str(chord_result.info)
        return status, result, error

    # Chord still in progress — calculate completion percentage
    # NOTE: This performs N individual Redis lookups (one per child task).
    # For very large batches a future optimisation can batch-fetch via
    # celery.result.GroupResult or a raw Redis MGET.
    status = "PROCESSING"
    try:
        total_files: int = result.get("file_count", len(result.get("file_ids", [])))
        child_task_ids: List[str] = result.get("child_task_ids", [])

        completed = sum(
            1
            for task_id in child_task_ids
            if AsyncResult(task_id, app=celery_app).ready()
        )

        progress = int((completed / total_files * 100)) if total_files > 0 else 0

        result = {
            "aggregated_file_id": "",
            "total_qa_pairs": 0,
            "successful_files": completed,
            "failed_files": 0,
            "status": "processing",
            "message": f"Processing {completed}/{total_files} files",
            "progress": progress,
            "completed_files": completed,
            "total_files": total_files,
        }
    except Exception:
        logger.exception("Failed to calculate chord progress for chord_id=%s", chord_id)
        result = {
            "aggregated_file_id": "",
            "total_qa_pairs": 0,
            "successful_files": 0,
            "failed_files": 0,
            "status": "processing",
            "message": "Processing...",
            "progress": 0,
            "completed_files": 0,
            "total_files": 0,
        }

    return status, result, error


@router.post("", response_model=PrepareDataResponse)
async def prepare_data(
    file_ids: List[str] = Body(..., embed=True, description="File IDs to process"),
    quality_threshold: float = 0.0,
    user_id: str = Depends(get_current_user_id),
):
    """
    Submit files for data preparation.
    Processes your files and generates training data in JSONL format.
    Returns a job ID to track the processing status.
    """
    if not file_ids:
        raise HTTPException(status_code=400, detail="At least one file ID is required")

    if len(file_ids) > MAX_FILE_IDS_PER_JOB:
        raise HTTPException(
            status_code=400,
            detail=f"Too many file IDs. Maximum allowed per job is {MAX_FILE_IDS_PER_JOB}.",
        )

    try:
        task = celery_app.send_task(
            "core.celery.tasks.dataset_generation_using_data_kits",
            args=[file_ids, user_id],
            queue="dataprep_queue",
        )

        # Store job metadata in Redis so user can retrieve it later
        metadata_stored = store_job_metadata(
            job_id=task.id,
            user_id=user_id,
            file_id=",".join(file_ids),
            metadata={
                "task_name": "dataset_generation_using_data_kits",
                "original_file_ids": file_ids,
                "file_count": len(file_ids),
                "processing_type": "parallel_chord_aggregation",
            },
        )

        if not metadata_stored:
            raise HTTPException(
                status_code=500,
                detail="Failed to store job metadata. Please retry.",
            )

        return {
            "submitted_job_ids": [task.id],
            "job_status": "Submitted",
            "result": None,
            "error": None,
            "file_count": len(file_ids),
            "processing_mode": "parallel_with_aggregation",
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Failed to submit batch job for user %s (%d files)", user_id, len(file_ids)
        )
        raise HTTPException(
            status_code=500,
            detail="An error occurred while submitting the job.",
        )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_prepare_data_status(job_id: str) -> Dict[str, Any]:
    """
    Get the status and result of your data preparation job.
    Returns the processed files when completed.
    """
    task_result = AsyncResult(job_id, app=celery_app)
    status, result, error = _resolve_chord_status(task_result)

    # If the parent task delegated to a chord, expose the chord's ID to the caller
    if (
        task_result.ready()
        and task_result.successful()
        and isinstance(task_result.result, dict)
        and "chord_id" in task_result.result
    ):
        job_id = task_result.result["chord_id"]

    return {
        "job_id": job_id,
        "status": status,
        "result": result,
        "error": error,
    }


@router.get("/jobs", response_model=JobListResponse)
async def get_all_jobs_by_user(
    user_id: str = Depends(get_current_user_id),
):
    """
    Get all your data preparation jobs.
    Returns a list of jobs with their current status.
    """
    jobs_metadata = get_jobs_by_user(user_id)

    if not jobs_metadata:
        return JobListResponse(user_id=user_id, total_jobs=0, jobs=[])

    jobs_with_status = []
    for job_meta in jobs_metadata:
        job_id = job_meta["job_id"]
        task_result = AsyncResult(job_id, app=celery_app)

        status, result, error = _resolve_chord_status(task_result)

        job_with_status = JobWithStatus(
            job_id=job_meta["job_id"],
            user_id=job_meta["user_id"],
            file_id=job_meta["file_id"],
            submitted_at=job_meta["submitted_at"],
            status=status,
            result=result,
            error=error,
            metadata=job_meta.get("metadata", {}),
        )
        jobs_with_status.append(job_with_status)

    return JobListResponse(
        user_id=user_id,
        total_jobs=len(jobs_with_status),
        jobs=jobs_with_status,
    )
