"""
Job metadata storage and retrieval utilities using Redis.
"""
import redis
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

# Get Redis connection URL
REDIS_URL = os.getenv(
    'CELERY_BROKER_URL',
    'redis://redis-broker-redis.dataprep.svc.cluster.local:6379/0'
)

# Parse Redis URL to create connection
def get_redis_client() -> redis.Redis:
    """Get Redis client connection."""
    return redis.from_url(REDIS_URL, decode_responses=True)


def store_job_metadata(job_id: str, user_id: str, file_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Store job metadata in Redis.

    Args:
        job_id: Celery job/task ID
        user_id: User who submitted the job
        file_id: File being processed
        metadata: Additional metadata to store

    Returns:
        bool: True if stored successfully
    """
    try:
        client = get_redis_client()

        job_data = {
            "job_id": job_id,
            "user_id": user_id,
            "file_id": file_id,
            "submitted_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        # Store job data with job_id as key
        job_key = f"job:{job_id}"
        client.setex(job_key, 86400, json.dumps(job_data))  # Expire after 24 hours

        # Add job_id to user's job list
        user_jobs_key = f"user_jobs:{user_id}"
        client.sadd(user_jobs_key, job_id)
        client.expire(user_jobs_key, 86400)  # Expire after 24 hours

        return True
    except Exception as e:
        print(f"Error storing job metadata: {e}")
        return False


def get_jobs_by_user(user_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all jobs for a specific user.

    Args:
        user_id: User ID to query jobs for

    Returns:
        List of job metadata dictionaries
    """
    try:
        client = get_redis_client()

        # Get all job IDs for this user
        user_jobs_key = f"user_jobs:{user_id}"
        job_ids = client.smembers(user_jobs_key)

        if not job_ids:
            return []

        # Retrieve metadata for each job
        jobs = []
        for job_id in job_ids:
            job_key = f"job:{job_id}"
            job_data_str = client.get(job_key)

            if job_data_str:
                job_data = json.loads(job_data_str)
                jobs.append(job_data)

        # Sort by submitted_at (most recent first)
        jobs.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)

        return jobs
    except Exception as e:
        print(f"Error retrieving jobs for user {user_id}: {e}")
        return []


def get_job_metadata(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve metadata for a specific job.

    Args:
        job_id: Celery job/task ID

    Returns:
        Job metadata dictionary or None if not found
    """
    try:
        client = get_redis_client()
        job_key = f"job:{job_id}"
        job_data_str = client.get(job_key)

        if job_data_str:
            return json.loads(job_data_str)
        return None
    except Exception as e:
        print(f"Error retrieving job metadata for {job_id}: {e}")
        return None


def delete_job_metadata(job_id: str, user_id: str) -> bool:
    """
    Delete job metadata from Redis.

    Args:
        job_id: Celery job/task ID
        user_id: User who owns the job

    Returns:
        bool: True if deleted successfully
    """
    try:
        client = get_redis_client()

        # Remove job data
        job_key = f"job:{job_id}"
        client.delete(job_key)

        # Remove from user's job list
        user_jobs_key = f"user_jobs:{user_id}"
        client.srem(user_jobs_key, job_id)

        return True
    except Exception as e:
        print(f"Error deleting job metadata: {e}")
        return False
