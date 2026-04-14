"""
SQLAlchemy ORM models for DocQvision database.

Defines database schema for templates, documents, extraction results,
and chat sessions with proper relationships and constraints.
"""

from sqlalchemy import Column, String, Integer, Text, LargeBinary, DateTime, ForeignKey, JSON, Float, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


class ExtractionStatus(enum.Enum):
    """Enumeration for extraction job status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ExtractionStage(enum.Enum):
    """Enumeration for extraction pipeline stage used."""
    TRADITIONAL = "traditional"
    VISION = "vision"
    MOCK = "mock"


class Template(Base):
    """
    Template model for storing document extraction schemas.

    Templates define what fields to extract from documents and their types.
    Users create templates via chat interface and reuse them for similar documents.

    Attributes:
        id: Unique template identifier
        name: User-provided template name
        doc_type: Document type category (invoice, prescription, contract, etc.)
        schema_json: JSON object defining extraction fields and their properties
        created_at: Timestamp when template was created
        updated_at: Timestamp when template was last modified
    """
    __tablename__ = "templates"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    doc_type = Column(String(100), nullable=False)
    schema_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    extractions = relationship("ExtractionResult", back_populates="template", cascade="all, delete-orphan")


class Document(Base):
    """
    Document model for storing uploaded PDF files.

    Stores PDF binary content and metadata for extraction processing.

    Attributes:
        id: Unique document identifier
        filename: Original filename from upload
        file_size: File size in bytes
        page_count: Number of pages in PDF
        sha256_hash: SHA-256 hash for deduplication and integrity
        file_content: Binary PDF content
        uploaded_at: Timestamp when document was uploaded
    """
    __tablename__ = "documents"

    id = Column(String(50), primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    page_count = Column(Integer, nullable=True)
    sha256_hash = Column(String(64), nullable=True, index=True)
    file_content = Column(LargeBinary, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    extractions = relationship("ExtractionResult", back_populates="document", cascade="all, delete-orphan")


class ExtractionResult(Base):
    """
    Extraction result model for storing extraction job history and results.

    Each extraction run creates a record with status, extracted data, and metadata.

    Attributes:
        id: Unique extraction result identifier
        document_id: Foreign key to document
        template_id: Foreign key to template used
        status: Current job status (pending, running, success, failed)
        stage_used: Pipeline stage that produced result (traditional, vision)
        extracted_data: JSON object with extracted field values
        field_coverage_percent: Percentage of required fields successfully extracted
        processing_time_ms: Total processing time in milliseconds
        model_used: Vision model identifier if vision stage was used
        error_message: Error details if extraction failed
        created_at: Timestamp when extraction job was created
    """
    __tablename__ = "extraction_results"

    id = Column(String(50), primary_key=True, index=True)
    document_id = Column(String(50), ForeignKey("documents.id"), nullable=False, index=True)
    template_id = Column(String(50), ForeignKey("templates.id"), nullable=False, index=True)
    status = Column(Enum(ExtractionStatus), nullable=False, default=ExtractionStatus.PENDING, index=True)
    stage_used = Column(Enum(ExtractionStage), nullable=True)
    extracted_data = Column(JSON, nullable=True)
    field_coverage_percent = Column(Float, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    model_used = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    document = relationship("Document", back_populates="extractions")
    template = relationship("Template", back_populates="extractions")
