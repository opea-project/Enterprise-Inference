"""Validation utilities for file uploads and data"""
import logging

logger = logging.getLogger(__name__)


def validate_pdf_file(content: bytes, filename: str) -> tuple[bool, str]:
    """
    Validate that uploaded file is a legitimate PDF

    Args:
        content: File bytes
        filename: Original filename

    Returns:
        (is_valid, error_message)
    """
    if not content:
        return False, "Empty file"

    if not filename.lower().endswith('.pdf'):
        return False, "Only PDF files are supported"

    if not content.startswith(b'%PDF-'):
        return False, "Invalid PDF file format (magic bytes mismatch)"

    if len(content) > 10 * 1024 * 1024:
        return False, "File size exceeds 10MB limit"

    return True, ""


def sanitize_chat_message(message: str) -> str:
    """
    Sanitize user chat input to prevent prompt injection

    Args:
        message: User chat message

    Returns:
        Sanitized message
    """
    if not message:
        return ""

    message = message.strip()

    if len(message) > 2000:
        message = message[:2000]

    suspicious_patterns = [
        "ignore previous",
        "ignore all previous",
        "disregard previous",
        "forget previous",
        "new instructions:",
        "system:",
        "assistant:",
    ]

    message_lower = message.lower()
    for pattern in suspicious_patterns:
        if pattern in message_lower:
            logger.warning(f"Potential prompt injection detected: {pattern}")

    return message
