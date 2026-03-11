"""
Vision-based extraction pipeline.

Extracts structured data from documents using AI vision model.
"""

import logging
import time
from typing import Dict, Any, Optional

import config
from models import ExtractionStage
from services.extractors import calculate_field_coverage
from services.pdf_utils import extract_text_by_page, select_relevant_pages
from services.vision_service import VisionService

logger = logging.getLogger(__name__)


class PipelineResult:
    """Container for pipeline execution results."""

    def __init__(
        self,
        extracted_data: Dict[str, Any],
        stage_used: ExtractionStage,
        field_coverage: float,
        processing_time_ms: int,
        model_used: Optional[str] = None
    ):
        self.extracted_data = extracted_data
        self.stage_used = stage_used
        self.field_coverage = field_coverage
        self.processing_time_ms = processing_time_ms
        self.model_used = model_used


class ExtractionPipeline:
    """
    Vision-based extraction pipeline.

    Extracts structured data from PDF documents using AI vision model,
    with intelligent page selection for multi-page documents.
    """

    def __init__(self):
        self.vision_service = VisionService()
        self.vision_max_pages = config.VISION_MAX_PAGES

        logger.info(f"Vision-only pipeline initialized (max pages: {self.vision_max_pages})")

    def extract(
        self,
        pdf_content: bytes,
        schema: Dict[str, Any],
        template_doc_type: str = None,
        validate_type: bool = True
    ) -> PipelineResult:
        """
        Execute vision-based extraction.

        Args:
            pdf_content: Binary PDF content
            schema: Extraction schema definition
            template_doc_type: Expected document type from template (e.g., "invoice", "prescription")
            validate_type: Whether to validate document type before extraction

        Returns:
            PipelineResult with extracted data and metadata

        Raises:
            ValueError: If extraction fails or document type mismatch
        """
        start_time = time.time()

        try:
            # Skip validation for test templates or if validation is disabled
            if validate_type and template_doc_type and template_doc_type.lower() != 'test':
                self._validate_document_type(pdf_content, template_doc_type)

            # Extract using vision model
            logger.info("Starting vision extraction")

            page_texts = extract_text_by_page(pdf_content)
            total_pages = len(page_texts)

            if total_pages > self.vision_max_pages:
                selected_pages = select_relevant_pages(
                    page_texts,
                    schema,
                    max_pages=self.vision_max_pages
                )
                logger.info(
                    f"Selected {len(selected_pages)} pages from {total_pages} total pages"
                )
            else:
                selected_pages = None

            extracted_data = self.vision_service.extract_with_schema(
                pdf_content,
                schema,
                page_numbers=selected_pages
            )

            coverage, field_status = calculate_field_coverage(extracted_data, schema)

            # Log missing fields for debugging
            missing_fields = [field for field, found in field_status.items() if not found]
            if missing_fields:
                logger.warning(
                    f"Vision extraction: {len(missing_fields)} fields not extracted: {missing_fields}"
                )

            logger.info(
                f"Vision extraction completed: coverage={coverage:.2%} "
                f"(extracted {len(extracted_data) - len(missing_fields)}/{len(schema)} fields)"
            )

            # Accept any coverage > 0
            if coverage == 0:
                error_msg = (
                    "Failed to extract data from document.\n\n"
                    "Possible reasons:\n"
                    "• Document type may not match the template\n"
                    "• Document quality or format may be incompatible\n"
                    "• Required fields may not be present in the document\n\n"
                    "Please verify:\n"
                    "1. You selected the correct template for this document type\n"
                    "2. The document contains the expected fields\n"
                    "3. The document is clear and readable"
                )
                raise ValueError(error_msg)

            processing_time = int((time.time() - start_time) * 1000)

            return PipelineResult(
                extracted_data=extracted_data,
                stage_used=ExtractionStage.VISION,
                field_coverage=coverage,
                processing_time_ms=processing_time,
                model_used=config.VISION_MODEL
            )

        except Exception as e:
            logger.error(f"Vision extraction failed: {str(e)}")
            raise ValueError(str(e))

    def _validate_document_type(self, pdf_content: bytes, expected_type: str):
        """
        Validate that document type matches expected template type.

        Args:
            pdf_content: Binary PDF content
            expected_type: Expected document type (e.g., "invoice", "prescription")

        Raises:
            ValueError: If document type doesn't match expected type
        """
        try:
            logger.info(f"Validating document type (expected: {expected_type})")

            detection_result = self.vision_service.detect_document_type(pdf_content)
            detected_type = detection_result.get("document_type", "unknown")
            confidence = detection_result.get("confidence", 0.0)
            reasoning = detection_result.get("reasoning", "")

            logger.info(
                f"Document type detection: {detected_type} "
                f"(confidence: {confidence:.1%}, expected: {expected_type})"
            )

            # Normalize types for comparison
            detected_normalized = detected_type.lower().replace("_", "").replace("-", "")
            expected_normalized = expected_type.lower().replace("_", "").replace("-", "")

            # Allow if confidence is low (uncertain detection)
            if confidence < 0.5:
                logger.warning(
                    f"Low confidence ({confidence:.1%}) in type detection. Proceeding with extraction."
                )
                return

            # Check for mismatch
            if detected_normalized != expected_normalized and confidence >= 0.7:
                error_msg = (
                    f"Document type mismatch detected!\n\n"
                    f"Expected: {expected_type.upper()}\n"
                    f"Detected: {detected_type.upper()} (confidence: {confidence:.0%})\n\n"
                    f"Reason: {reasoning}\n\n"
                    f"Please select the correct template for this document type, "
                    f"or upload a {expected_type} document."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.info("Document type validation passed")

        except ValueError:
            raise  # Re-raise validation errors
        except Exception as e:
            # Don't fail extraction if validation itself fails
            logger.warning(f"Document type validation failed: {str(e)}. Proceeding with extraction.")
