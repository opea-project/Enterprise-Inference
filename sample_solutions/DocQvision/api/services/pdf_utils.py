"""
PDF processing utilities for text extraction and page selection.

Provides multi-page text extraction and intelligent page selection for
token-constrained vision model fallback.
"""

import logging
from typing import List, Tuple, Optional
from io import BytesIO
from pypdf import PdfReader

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_content: bytes, max_pages: Optional[int] = None) -> str:
    """
    Extract text from all pages of PDF document.

    Args:
        pdf_content: Binary PDF content
        max_pages: Maximum number of pages to process (None for all pages)

    Returns:
        Concatenated text from all pages with page boundaries preserved
    """
    try:
        pdf_reader = PdfReader(BytesIO(pdf_content))
        total_pages = len(pdf_reader.pages)

        pages_to_process = min(total_pages, max_pages) if max_pages else total_pages

        text_parts = []
        for page_num in range(pages_to_process):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()

            if page_text.strip():
                text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")

        combined_text = "\n\n".join(text_parts)
        logger.info(f"Extracted text from {pages_to_process} pages ({len(combined_text)} chars)")

        return combined_text

    except Exception as e:
        logger.error(f"PDF text extraction failed: {str(e)}")
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")


def extract_text_by_page(pdf_content: bytes) -> List[Tuple[int, str]]:
    """
    Extract text from PDF with per-page granularity.

    Args:
        pdf_content: Binary PDF content

    Returns:
        List of (page_number, page_text) tuples
    """
    try:
        pdf_reader = PdfReader(BytesIO(pdf_content))
        page_texts = []

        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            page_texts.append((page_num + 1, page_text))

        logger.info(f"Extracted {len(page_texts)} pages individually")
        return page_texts

    except Exception as e:
        logger.error(f"Per-page text extraction failed: {str(e)}")
        raise ValueError(f"Failed to extract text by page: {str(e)}")


def select_relevant_pages(
    page_texts: List[Tuple[int, str]],
    schema: dict,
    max_pages: int = 3
) -> List[int]:
    """
    Select most relevant pages for vision model processing based on schema fields.

    Uses keyword matching to identify pages likely containing target fields.

    Args:
        page_texts: List of (page_number, page_text) tuples
        schema: Schema definition with field names
        max_pages: Maximum number of pages to select

    Returns:
        List of selected page numbers (1-indexed)
    """
    if len(page_texts) <= max_pages:
        return [page_num for page_num, _ in page_texts]

    field_keywords = []
    for field_name in schema.keys():
        keywords = field_name.lower().replace('_', ' ').split()
        field_keywords.extend(keywords)

    page_scores = []
    for page_num, page_text in page_texts:
        page_text_lower = page_text.lower()
        score = sum(1 for keyword in field_keywords if keyword in page_text_lower)

        text_density = len(page_text.strip())
        combined_score = score * 10 + (text_density / 1000)

        page_scores.append((page_num, combined_score))

    page_scores.sort(key=lambda x: x[1], reverse=True)
    selected_pages = sorted([page_num for page_num, _ in page_scores[:max_pages]])

    logger.info(f"Selected pages {selected_pages} from {len(page_texts)} total pages")
    return selected_pages


def get_page_count(pdf_content: bytes) -> int:
    """
    Get total page count from PDF document.

    Args:
        pdf_content: Binary PDF content

    Returns:
        Number of pages in PDF
    """
    try:
        pdf_reader = PdfReader(BytesIO(pdf_content))
        return len(pdf_reader.pages)
    except Exception as e:
        logger.error(f"Failed to get page count: {str(e)}")
        return 0
