"""
DocQvision API - Document Intelligence Platform

FastAPI application providing REST endpoints for template-based document extraction
using AI vision models. Supports chat-based schema configuration, PDF upload,
data extraction, and result export.
"""

import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import uvicorn
import json

import config
from database import get_db, init_db
from services.extraction_service import ExtractionService
from utils.validators import validate_pdf_file, sanitize_chat_message
import crud
import schemas

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DocQvision API",
    description="Document Intelligence Platform API - Extract structured data from PDF documents using AI vision models",
    version="1.0.0"
)

origins = config.CORS_ORIGINS.split(",") if config.CORS_ORIGINS != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

extraction_service = ExtractionService()


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Global exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


@app.get("/")
def root():
    """Root endpoint with service information."""
    return {
        "message": "DocQvision API is running",
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs",
        "inference_endpoint": config.INFERENCE_API_ENDPOINT,
        "vision_model": config.VISION_MODEL
    }


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": "DocQvision",
        "version": "1.0.0"
    }


@app.post("/api/configure")
async def configure_schema(
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Process chat message to build extraction schema with session isolation.

    Uses conversational AI to help users define extraction fields interactively.
    Each session maintains independent chat history and schema.

    Args:
        message: User's natural language message
        session_id: Optional session identifier for chat isolation
        db: Database session

    Returns:
        AI reply with updated schema definition and session_id
    """
    try:
        if not message or not message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        sanitized_message = sanitize_chat_message(message)
        result = extraction_service.process_chat_message(sanitized_message, session_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in configure endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/configure/clear")
async def clear_chat_session(session_id: str = Form(...)):
    """
    Clear/reset a chat session.

    Args:
        session_id: Session identifier to clear

    Returns:
        Success confirmation
    """
    try:
        result = extraction_service.clear_session(session_id)
        return result
    except Exception as e:
        logger.error(f"Error clearing session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/templates", response_model=schemas.TemplateResponse)
def create_template(
    template: schemas.TemplateCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new extraction template.

    Args:
        template: Template creation data with name, type, and schema
        db: Database session

    Returns:
        Created template with ID and timestamps
    """
    try:
        db_template = crud.create_template(db, template)
        logger.info(f"Template created: {db_template.id}")
        return db_template
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/templates", response_model=List[schemas.TemplateListItem])
def list_templates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve all templates with pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session

    Returns:
        List of template summaries
    """
    try:
        templates = crud.get_templates(db, skip=skip, limit=limit)
        return templates
    except Exception as e:
        logger.error(f"Error listing templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/templates/{template_id}", response_model=schemas.TemplateResponse)
def get_template(
    template_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve template by ID.

    Args:
        template_id: Template identifier
        db: Database session

    Returns:
        Template details with full schema
    """
    template = crud.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@app.put("/api/templates/{template_id}", response_model=schemas.TemplateResponse)
def update_template(
    template_id: str,
    template_update: schemas.TemplateUpdate,
    db: Session = Depends(get_db)
):
    """
    Update existing template.

    Args:
        template_id: Template identifier
        template_update: Fields to update
        db: Database session

    Returns:
        Updated template
    """
    updated_template = crud.update_template(db, template_id, template_update)
    if not updated_template:
        raise HTTPException(status_code=404, detail="Template not found")

    logger.info(f"Template updated: {template_id}")
    return updated_template


@app.delete("/api/templates/{template_id}")
def delete_template(
    template_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete template by ID.

    Args:
        template_id: Template identifier
        db: Database session

    Returns:
        Success confirmation
    """
    deleted = crud.delete_template(db, template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")

    logger.info(f"Template deleted: {template_id}")
    return {"success": True, "message": "Template deleted successfully"}


@app.post("/api/templates/save")
async def save_template_from_chat(
    name: str = Form(...),
    template_type: str = Form(...),
    schema: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Save template from chat configuration.

    Converts flat schema format to nested format and saves to database.

    Args:
        name: Template name
        template_type: Document type
        schema: JSON string with schema definition
        db: Database session

    Returns:
        Success confirmation with template ID
    """
    try:
        schema_dict = json.loads(schema)

        def convert_to_field_schema(field_type):
            """Convert field type string to FieldSchema object."""
            if isinstance(field_type, dict):
                return field_type
            return {
                "type": field_type,
                "required": True
            }

        nested_schema = {}
        for field_name, field_type in schema_dict.items():
            nested_schema[field_name] = convert_to_field_schema(field_type)

        template_create = schemas.TemplateCreate(
            name=name,
            doc_type=template_type,
            schema_json=nested_schema
        )

        db_template = crud.create_template(db, template_create)
        logger.info(f"Template saved: {db_template.id}")

        return {
            "success": True,
            "template_id": db_template.id,
            "message": f"Template '{name}' saved successfully"
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid schema format")
    except Exception as e:
        logger.error(f"Error saving template: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/upload", response_model=schemas.DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload PDF document to database.

    Args:
        file: PDF file upload
        db: Database session

    Returns:
        Document metadata with ID
    """
    try:
        content = await file.read()

        is_valid, error_msg = validate_pdf_file(content, file.filename)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        if len(content) > config.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds {config.MAX_FILE_SIZE // (1024*1024)}MB limit"
            )

        db_document = crud.create_document(db, file.filename, content)
        logger.info(f"Document uploaded: {db_document.id} ({file.filename})")

        return schemas.DocumentUploadResponse(
            document_id=db_document.id,
            filename=db_document.filename,
            file_size=db_document.file_size,
            page_count=db_document.page_count,
            uploaded_at=db_document.uploaded_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/batch-upload")
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload multiple PDF documents in batch.

    Args:
        files: List of PDF file uploads
        db: Database session

    Returns:
        List of document upload responses with success/error status
    """
    if len(files) > config.MAX_BATCH_UPLOAD:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {config.MAX_BATCH_UPLOAD} files allowed per batch upload"
        )

    results = []
    for file in files:
        try:
            content = await file.read()

            is_valid, error_msg = validate_pdf_file(content, file.filename)
            if not is_valid:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": error_msg
                })
                continue

            if len(content) > config.MAX_FILE_SIZE:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": f"File size exceeds {config.MAX_FILE_SIZE // (1024*1024)}MB limit"
                })
                continue

            db_document = crud.create_document(db, file.filename, content)
            logger.info(f"Batch upload - Document uploaded: {db_document.id} ({file.filename})")

            results.append({
                "filename": file.filename,
                "success": True,
                "document_id": db_document.id,
                "file_size": db_document.file_size,
                "page_count": db_document.page_count
            })

        except Exception as e:
            logger.error(f"Error uploading {file.filename}: {str(e)}")
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })

    successful_uploads = sum(1 for r in results if r["success"])
    logger.info(f"Batch upload completed: {successful_uploads}/{len(files)} files uploaded successfully")

    return {
        "total_files": len(files),
        "successful": successful_uploads,
        "failed": len(files) - successful_uploads,
        "results": results
    }


@app.post("/api/extract", response_model=schemas.ExtractionResponse)
async def create_extraction_job(
    extraction: schemas.ExtractionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create extraction job and process in background.

    Args:
        extraction: Extraction job parameters (document_id, template_id)
        background_tasks: FastAPI background task handler
        db: Database session

    Returns:
        Extraction job with initial status (pending)
    """
    try:
        document = crud.get_document(db, extraction.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        template = crud.get_template(db, extraction.template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        db_result = crud.create_extraction_result(db, extraction.document_id, extraction.template_id)

        background_tasks.add_task(
            extraction_service.process_extraction_job,
            db_result.id,
            document.file_content,
            template.schema_json,
            template.doc_type
        )

        logger.info(f"Extraction job created: {db_result.id} (template type: {template.doc_type})")
        return db_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating extraction job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/extract/{job_id}", response_model=schemas.ExtractionResponse)
def get_extraction_result(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve extraction job status and results.

    Poll this endpoint to check job completion status.

    Args:
        job_id: Extraction job identifier
        db: Database session

    Returns:
        Extraction job details with status and results
    """
    result = crud.get_extraction_result(db, job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Extraction job not found")
    return result


@app.get("/api/history", response_model=List[schemas.ExtractionResponse])
def get_extraction_history(
    template_id: Optional[str] = None,
    status: Optional[schemas.ExtractionStatusEnum] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Retrieve extraction history with optional filtering.

    Args:
        template_id: Filter by template ID
        status: Filter by extraction status
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session

    Returns:
        List of extraction results ordered by creation time (newest first)
    """
    try:
        status_enum = None
        if status:
            from models import ExtractionStatus
            status_enum = ExtractionStatus[status.value.upper()]

        results = crud.get_extraction_history(
            db,
            template_id=template_id,
            status=status_enum,
            skip=skip,
            limit=limit
        )

        # Enrich results with document and template info
        enriched_results = []
        for result in results:
            result_dict = {
                "id": result.id,
                "document_id": result.document_id,
                "template_id": result.template_id,
                "status": result.status.value,
                "stage_used": result.stage_used.value if result.stage_used else None,
                "extracted_data": result.extracted_data,
                "field_coverage_percent": result.field_coverage_percent,
                "processing_time_ms": result.processing_time_ms,
                "model_used": result.model_used,
                "error_message": result.error_message,
                "created_at": result.created_at,
                "document_filename": result.document.filename if result.document else None,
                "template_name": result.template.name if result.template else None,
                "document_page_count": result.document.page_count if result.document else None
            }
            enriched_results.append(result_dict)

        return enriched_results
    except Exception as e:
        logger.error(f"Error retrieving extraction history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/extract/{job_id}")
def delete_extraction(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete extraction result by ID.

    Args:
        job_id: Extraction job identifier
        db: Database session

    Returns:
        Success confirmation
    """
    result = crud.get_extraction_result(db, job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Extraction job not found")

    db.delete(result)
    db.commit()
    logger.info(f"Extraction job deleted: {job_id}")
    return {"success": True, "message": "Extraction deleted successfully"}


@app.post("/api/extract/{job_id}/re-extract", response_model=schemas.ExtractionResponse)
async def re_extract_document(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Re-run extraction on an existing extraction result.

    Args:
        job_id: Existing extraction job identifier
        background_tasks: FastAPI background task handler
        db: Database session

    Returns:
        New extraction job with initial status (pending)
    """
    try:
        original_result = crud.get_extraction_result(db, job_id)
        if not original_result:
            raise HTTPException(status_code=404, detail="Original extraction job not found")

        document = crud.get_document(db, original_result.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        template = crud.get_template(db, original_result.template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Create new extraction result
        db_result = crud.create_extraction_result(db, document.id, template.id)

        background_tasks.add_task(
            extraction_service.process_extraction_job,
            db_result.id,
            document.file_content,
            template.schema_json,
            template.doc_type
        )

        logger.info(f"Re-extraction job created: {db_result.id} from original: {job_id}")
        return db_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating re-extraction job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Initialize database and log startup information."""
    logger.info("=" * 60)
    logger.info("DocQvision API Starting")
    logger.info(f"Environment: {config.ENVIRONMENT}")
    logger.info(f"Database: {config.DATABASE_URL}")
    logger.info(f"Inference endpoint: {config.INFERENCE_API_ENDPOINT}")
    logger.info(f"Vision Model: {config.VISION_MODEL}")
    logger.info(f"Detection Model: {config.DETECTION_MODEL}")

    try:
        config.validate_auth_config()
        logger.info("Authentication configuration validated")
    except ValueError as e:
        logger.error(f"Authentication configuration error: {str(e)}")
        raise

    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise

    logger.info("=" * 60)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
