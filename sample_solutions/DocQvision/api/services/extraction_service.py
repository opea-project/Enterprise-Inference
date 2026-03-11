"""
Extraction service for document processing.

Handles template management, document upload, and data extraction workflows.
Coordinates multi-stage extraction pipeline and database persistence.
"""

import uuid
import logging
import time
from datetime import datetime
from typing import Dict, Any
from services.vision_service import VisionService
from services.extraction_pipeline import ExtractionPipeline
from database import SessionLocal
import crud
from models import ExtractionStatus, ExtractionStage

logger = logging.getLogger(__name__)


class ExtractionService:
    def __init__(self):
        self.templates = self._initialize_templates()
        self.documents = {}
        self.chat_sessions = {}
        self.vision_service = VisionService()
        self.extraction_pipeline = ExtractionPipeline()

    def _initialize_templates(self):
        """Initialize with default templates"""
        return {
            "invoice": {
                "id": "invoice",
                "name": "Invoice Template",
                "type": "invoice",
                "schema": {
                    "invoice_number": "string",
                    "date": "date",
                    "vendor": "string",
                    "total": "number"
                }
            },
            "prescription": {
                "id": "prescription",
                "name": "Prescription Template",
                "type": "prescription",
                "schema": {
                    "patient_name": "string",
                    "medication": "string",
                    "dosage": "string",
                    "date": "date"
                }
            },
            "contract": {
                "id": "contract",
                "name": "Contract Template",
                "type": "contract",
                "schema": {
                    "party_1": "string",
                    "party_2": "string",
                    "date": "date",
                    "terms": "string"
                }
            }
        }

    def _get_or_create_session(self, session_id: str):
        """Get or create chat session by ID"""
        if session_id not in self.chat_sessions:
            self.chat_sessions[session_id] = {
                "schema": {},
                "chat_history": [],
                "created_at": datetime.now().isoformat()
            }
            logger.info(f"Created new chat session: {session_id}")
        return self.chat_sessions[session_id]

    def process_chat_message(self, message: str, session_id: str = None):
        """Process chat message with AI assistance in isolated session"""
        try:
            if not session_id:
                session_id = str(uuid.uuid4())

            session = self._get_or_create_session(session_id)

            session["chat_history"].append({"role": "user", "content": message})

            reply, updated_schema = self.vision_service.process_chat_message(
                message, session["schema"]
            )

            session["schema"] = updated_schema
            session["chat_history"].append({"role": "assistant", "content": reply})

            logger.info(f"Chat processed for session {session_id}. Schema has {len(session['schema'])} fields")

            return {
                "reply": reply,
                "schema": session["schema"],
                "chat_history": session["chat_history"],
                "session_id": session_id
            }
        except Exception as e:
            logger.error(f"Error processing chat message: {str(e)}")
            error_reply = "I encountered an error processing your message. Please try again."
            session = self._get_or_create_session(session_id or str(uuid.uuid4()))
            session["chat_history"].append({"role": "assistant", "content": error_reply})
            return {
                "reply": error_reply,
                "schema": session["schema"],
                "chat_history": session["chat_history"],
                "session_id": session_id
            }

    def clear_session(self, session_id: str):
        """Clear/delete a chat session"""
        if session_id in self.chat_sessions:
            del self.chat_sessions[session_id]
            logger.info(f"Cleared chat session: {session_id}")
            return {"success": True, "message": "Session cleared"}
        return {"success": False, "message": "Session not found"}

    def save_template(self, name: str, template_type: str, schema: Dict[str, str]) -> Dict[str, Any]:
        """Save a new template"""
        try:
            template_id = template_type.lower().replace(" ", "_")

            template = {
                "id": template_id,
                "name": name,
                "type": template_type,
                "schema": schema,
                "created_at": datetime.now().isoformat()
            }

            self.templates[template_id] = template
            logger.info(f"Template saved: {template_id}")

            return {
                "success": True,
                "template_id": template_id,
                "message": f"Template '{name}' saved successfully"
            }
        except Exception as e:
            logger.error(f"Error saving template: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def upload_file(self, filename: str, content: bytes):
        """Upload and store document"""
        try:
            if len(content) > 10 * 1024 * 1024:
                raise ValueError("File size exceeds 10MB limit")

            document_id = str(uuid.uuid4())
            self.documents[document_id] = {
                "id": document_id,
                "filename": filename,
                "content": content,
                "size": len(content),
                "uploaded_at": datetime.now().isoformat()
            }

            logger.info(f"Document uploaded: {document_id} ({filename})")

            return {
                "document_id": document_id,
                "filename": filename,
                "size": len(content),
                "status": "uploaded"
            }
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise

    def extract_document(self, document_id: str, template_id: str):
        """Extract data from document using vision AI"""
        start_time = time.time()

        try:
            if document_id not in self.documents:
                raise ValueError(f"Document not found: {document_id}")

            if template_id not in self.templates:
                raise ValueError(f"Template not found: {template_id}")

            document = self.documents[document_id]
            template = self.templates[template_id]
            schema = template["schema"]

            logger.info(f"Extracting document {document_id} with template {template_id}")

            extracted_data = self.vision_service.extract_with_schema(
                document["content"],
                schema
            )

            processing_time = int((time.time() - start_time) * 1000)

            result = {
                "result_id": str(uuid.uuid4()),
                "document_id": document_id,
                "template_id": template_id,
                "extracted_data": extracted_data,
                "status": "completed",
                "processing_time_ms": processing_time
            }

            logger.info(f"Extraction completed in {processing_time}ms")

            return result

        except Exception as e:
            logger.error(f"Error extracting document: {str(e)}")
            raise

    def get_templates(self):
        """Get all available templates"""
        return {
            "templates": [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "type": t["type"]
                }
                for t in self.templates.values()
            ]
        }

    def process_extraction_job(self, job_id: str, pdf_content: bytes, schema: Dict[str, Any], template_doc_type: str = None) -> None:
        """
        Process extraction job through vision-based pipeline in background.

        Executes vision extraction pipeline with intelligent page selection
        and document type validation. Updates database with status and results
        throughout execution.

        Args:
            job_id: Extraction result ID in database
            pdf_content: Binary PDF content
            schema: Template schema definition
            template_doc_type: Expected document type for validation
        """
        db = SessionLocal()

        try:
            crud.update_extraction_result(
                db,
                job_id,
                status=ExtractionStatus.RUNNING
            )

            logger.info(f"Starting extraction job: {job_id} (template type: {template_doc_type})")

            result = self.extraction_pipeline.extract(
                pdf_content,
                schema,
                template_doc_type=template_doc_type,
                validate_type=True
            )

            crud.update_extraction_result(
                db,
                job_id,
                status=ExtractionStatus.SUCCESS,
                stage_used=result.stage_used,
                extracted_data=result.extracted_data,
                field_coverage_percent=result.field_coverage,
                processing_time_ms=result.processing_time_ms,
                model_used=result.model_used
            )

            logger.info(
                f"Extraction job completed: {job_id} "
                f"(stage={result.stage_used.value}, coverage={result.field_coverage:.2%}, "
                f"time={result.processing_time_ms}ms)"
            )

        except Exception as e:
            logger.error(f"Extraction job failed: {job_id} - {str(e)}")

            crud.update_extraction_result(
                db,
                job_id,
                status=ExtractionStatus.FAILED,
                error_message=str(e)
            )

        finally:
            db.close()
