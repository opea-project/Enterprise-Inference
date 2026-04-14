from pydantic import BaseModel
from typing import Optional, List


class FileObject(BaseModel):
    """Schema for file metadata"""
    id: str
    object: str = "file"
    bytes: int
    created_at: int
    filename: str
    purpose: str
    status: str = "processed"
    status_details: Optional[str] = None


class DeleteResponse(BaseModel):
    """Schema for file deletion response"""
    id: str
    object: str = "file"
    deleted: bool


class DataPrepRequest(BaseModel):
    """Schema for data preparation request"""
    file_ids: List[str]
    format: str = "jsonl"
