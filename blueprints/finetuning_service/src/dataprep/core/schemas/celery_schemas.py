from pydantic import BaseModel
from typing import Optional, List, Any, Dict

class TaskSubmit(BaseModel):
    task_name: str
    task_args: list = []
    task_kwargs: dict = {}

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskResult(BaseModel):
    task_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None

class JobMetadata(BaseModel):
    job_id: str
    user_id: str
    file_id: str
    submitted_at: str
    metadata: Dict[str, Any] = {}

class JobWithStatus(BaseModel):
    job_id: str
    user_id: str
    file_id: str
    submitted_at: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}

class JobListResponse(BaseModel):
    user_id: str
    total_jobs: int
    jobs: List[JobWithStatus]

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None

class PrepareDataResponse(BaseModel):
    submitted_job_ids: List[str]
