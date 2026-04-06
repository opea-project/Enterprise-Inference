from celery import Celery
import os

# Get Redis broker URL from environment variable
REDIS_BROKER_URL = os.getenv(
    'CELERY_BROKER_URL', ""
)

# Create Celery app instance
celery_app = Celery(
    'dataprep_tasks',
    broker=REDIS_BROKER_URL,
    backend=REDIS_BROKER_URL,
    include=['core.celery.tasks']
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=7200,  # 2 hours max per task
    result_expires=604800,  # Results expire after 7 days
)