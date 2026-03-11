"""
Pydantic schemas for request/response validation.

Defines data validation models for API endpoints, ensuring type safety
and proper data structure throughout the application.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ExtractionStatusEnum(str, Enum):
    """Extraction job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ExtractionStageEnum(str, Enum):
    """Extraction pipeline stage enumeration."""
    TRADITIONAL = "traditional"
    VISION = "vision"
    MOCK = "mock"


class FieldSchema(BaseModel):
    """
    Schema definition for a single extraction field.

    Attributes:
        type: Field data type (string, number, date, boolean)
        required: Whether field must be extracted
        description: Optional field description for UI
        enum: Optional list of allowed values
    """
    type: str = Field(..., description="Field data type")
    required: bool = Field(default=True, description="Whether field is required")
    description: Optional[str] = Field(default=None, description="Field description")
    enum: Optional[List[str]] = Field(default=None, description="Allowed values for enum fields")

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate field type is one of allowed types."""
        allowed_types = {'string', 'number', 'date', 'boolean', 'array', 'object'}
        if v not in allowed_types:
            raise ValueError(f"Field type must be one of {allowed_types}")
        return v


class TemplateCreate(BaseModel):
    """Schema for creating a new template."""
    model_config = {"protected_namespaces": ()}

    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    doc_type: str = Field(..., min_length=1, max_length=100, description="Document type")
    schema_json: Dict[str, FieldSchema] = Field(..., description="Extraction schema definition")


class TemplateUpdate(BaseModel):
    """Schema for updating an existing template."""
    model_config = {"protected_namespaces": ()}

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    doc_type: Optional[str] = Field(None, min_length=1, max_length=100)
    schema_json: Optional[Dict[str, FieldSchema]] = None


class TemplateResponse(BaseModel):
    """Schema for template response."""
    model_config = {"from_attributes": True, "protected_namespaces": ()}

    id: str
    name: str
    doc_type: str
    schema_json: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TemplateListItem(BaseModel):
    """Schema for template list item (without full schema)."""
    id: str
    name: str
    doc_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    """Schema for document upload response."""
    document_id: str
    filename: str
    file_size: int
    page_count: Optional[int]
    uploaded_at: datetime


class ExtractionCreate(BaseModel):
    """Schema for creating extraction job."""
    document_id: str = Field(..., description="Document ID to extract from")
    template_id: str = Field(..., description="Template ID to use for extraction")


class ExtractionResponse(BaseModel):
    """Schema for extraction job response."""
    model_config = {"from_attributes": True, "protected_namespaces": ()}

    id: str
    document_id: str
    template_id: str
    status: ExtractionStatusEnum
    stage_used: Optional[ExtractionStageEnum]
    extracted_data: Optional[Dict[str, Any]]
    field_coverage_percent: Optional[float]
    processing_time_ms: Optional[int]
    model_used: Optional[str]
    error_message: Optional[str]
    created_at: datetime

    # Additional fields for UI
    document_filename: Optional[str] = None
    template_name: Optional[str] = None
    document_page_count: Optional[int] = None


class ChatMessage(BaseModel):
    """Schema for chat message."""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    """Schema for chat configuration request."""
    message: str = Field(..., min_length=1, description="User message")
    session_id: Optional[str] = Field(default=None, description="Existing session ID to continue")


class ChatResponse(BaseModel):
    """Schema for chat configuration response."""
    model_config = {"protected_namespaces": ()}

    session_id: str
    reply: str
    schema: Dict[str, Any]
    messages: List[ChatMessage]


class ExtractionHistoryFilter(BaseModel):
    """Schema for extraction history filtering."""
    template_id: Optional[str] = None
    status: Optional[ExtractionStatusEnum] = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
