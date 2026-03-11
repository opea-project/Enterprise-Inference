"""
CRUD operations for database models.

Provides create, read, update, delete operations for templates, documents,
and extraction results.
"""

from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import models
import schemas
import uuid
import hashlib
from datetime import datetime


# Template CRUD operations

def create_template(db: Session, template: schemas.TemplateCreate) -> models.Template:
    """
    Create a new template in database.

    Args:
        db: Database session
        template: Template creation data

    Returns:
        Created template model instance
    """
    template_id = str(uuid.uuid4())
    db_template = models.Template(
        id=template_id,
        name=template.name,
        doc_type=template.doc_type,
        schema_json={k: v.model_dump() for k, v in template.schema_json.items()}
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


def get_template(db: Session, template_id: str) -> Optional[models.Template]:
    """
    Retrieve template by ID.

    Args:
        db: Database session
        template_id: Template identifier

    Returns:
        Template model instance or None if not found
    """
    return db.query(models.Template).filter(models.Template.id == template_id).first()


def get_templates(db: Session, skip: int = 0, limit: int = 100) -> List[models.Template]:
    """
    Retrieve all templates with pagination.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of template model instances
    """
    return db.query(models.Template).order_by(models.Template.created_at.desc()).offset(skip).limit(limit).all()


def get_templates_by_doc_type(db: Session, doc_type: str) -> List[models.Template]:
    """
    Retrieve templates matching a specific document type.

    Args:
        db: Database session
        doc_type: Document type to filter by

    Returns:
        List of template model instances matching the document type
    """
    normalized_doc_type = doc_type.lower().replace("_", "").replace("-", "")

    all_templates = db.query(models.Template).all()
    matching_templates = []

    for template in all_templates:
        if template.doc_type:
            normalized_template_type = template.doc_type.lower().replace("_", "").replace("-", "")
            if normalized_template_type == normalized_doc_type:
                matching_templates.append(template)

    return sorted(matching_templates, key=lambda t: t.created_at, reverse=True)


def update_template(db: Session, template_id: str, template_update: schemas.TemplateUpdate) -> Optional[models.Template]:
    """
    Update existing template.

    Args:
        db: Database session
        template_id: Template identifier
        template_update: Fields to update

    Returns:
        Updated template model instance or None if not found
    """
    db_template = get_template(db, template_id)
    if not db_template:
        return None

    update_data = template_update.model_dump(exclude_unset=True)
    if 'schema_json' in update_data and update_data['schema_json']:
        update_data['schema_json'] = {k: v.model_dump() for k, v in update_data['schema_json'].items()}

    for field, value in update_data.items():
        setattr(db_template, field, value)

    db.commit()
    db.refresh(db_template)
    return db_template


def delete_template(db: Session, template_id: str) -> bool:
    """
    Delete template by ID.

    Args:
        db: Database session
        template_id: Template identifier

    Returns:
        True if deleted, False if not found
    """
    db_template = get_template(db, template_id)
    if not db_template:
        return False

    db.delete(db_template)
    db.commit()
    return True


# Document CRUD operations

def create_document(db: Session, filename: str, file_content: bytes, page_count: Optional[int] = None) -> models.Document:
    """
    Create a new document in database.

    Args:
        db: Database session
        filename: Original filename
        file_content: Binary PDF content
        page_count: Number of pages in PDF

    Returns:
        Created document model instance
    """
    document_id = str(uuid.uuid4())
    sha256_hash = hashlib.sha256(file_content).hexdigest()

    db_document = models.Document(
        id=document_id,
        filename=filename,
        file_size=len(file_content),
        page_count=page_count,
        sha256_hash=sha256_hash,
        file_content=file_content
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document


def get_document(db: Session, document_id: str) -> Optional[models.Document]:
    """
    Retrieve document by ID.

    Args:
        db: Database session
        document_id: Document identifier

    Returns:
        Document model instance or None if not found
    """
    return db.query(models.Document).filter(models.Document.id == document_id).first()


def get_document_by_hash(db: Session, sha256_hash: str) -> Optional[models.Document]:
    """
    Retrieve document by SHA-256 hash for deduplication.

    Args:
        db: Database session
        sha256_hash: SHA-256 hash of file content

    Returns:
        Document model instance or None if not found
    """
    return db.query(models.Document).filter(models.Document.sha256_hash == sha256_hash).first()


# Extraction Result CRUD operations

def create_extraction_result(
    db: Session,
    document_id: str,
    template_id: str
) -> models.ExtractionResult:
    """
    Create a new extraction result record with pending status.

    Args:
        db: Database session
        document_id: Document identifier
        template_id: Template identifier

    Returns:
        Created extraction result model instance
    """
    result_id = str(uuid.uuid4())
    db_result = models.ExtractionResult(
        id=result_id,
        document_id=document_id,
        template_id=template_id,
        status=models.ExtractionStatus.PENDING
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result


def update_extraction_result(
    db: Session,
    result_id: str,
    status: Optional[models.ExtractionStatus] = None,
    stage_used: Optional[models.ExtractionStage] = None,
    extracted_data: Optional[Dict[str, Any]] = None,
    field_coverage_percent: Optional[float] = None,
    processing_time_ms: Optional[int] = None,
    model_used: Optional[str] = None,
    error_message: Optional[str] = None
) -> Optional[models.ExtractionResult]:
    """
    Update extraction result with processing results.

    Args:
        db: Database session
        result_id: Extraction result identifier
        status: Job status
        stage_used: Pipeline stage that produced result
        extracted_data: Extracted field values
        field_coverage_percent: Coverage percentage
        processing_time_ms: Processing time
        model_used: Model identifier
        error_message: Error details

    Returns:
        Updated extraction result model instance or None if not found
    """
    db_result = db.query(models.ExtractionResult).filter(models.ExtractionResult.id == result_id).first()
    if not db_result:
        return None

    if status is not None:
        db_result.status = status
    if stage_used is not None:
        db_result.stage_used = stage_used
    if extracted_data is not None:
        db_result.extracted_data = extracted_data
    if field_coverage_percent is not None:
        db_result.field_coverage_percent = field_coverage_percent
    if processing_time_ms is not None:
        db_result.processing_time_ms = processing_time_ms
    if model_used is not None:
        db_result.model_used = model_used
    if error_message is not None:
        db_result.error_message = error_message

    db.commit()
    db.refresh(db_result)
    return db_result


def get_extraction_result(db: Session, result_id: str) -> Optional[models.ExtractionResult]:
    """
    Retrieve extraction result by ID.

    Args:
        db: Database session
        result_id: Extraction result identifier

    Returns:
        Extraction result model instance or None if not found
    """
    return db.query(models.ExtractionResult).filter(models.ExtractionResult.id == result_id).first()


def get_extraction_history(
    db: Session,
    template_id: Optional[str] = None,
    status: Optional[models.ExtractionStatus] = None,
    skip: int = 0,
    limit: int = 50
) -> List[models.ExtractionResult]:
    """
    Retrieve extraction history with optional filtering.

    Args:
        db: Database session
        template_id: Filter by template ID
        status: Filter by status
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of extraction result model instances with document and template relationships loaded
    """
    from sqlalchemy.orm import joinedload

    query = db.query(models.ExtractionResult).options(
        joinedload(models.ExtractionResult.document),
        joinedload(models.ExtractionResult.template)
    )

    if template_id:
        query = query.filter(models.ExtractionResult.template_id == template_id)
    if status:
        query = query.filter(models.ExtractionResult.status == status)

    return query.order_by(models.ExtractionResult.created_at.desc()).offset(skip).limit(limit).all()
