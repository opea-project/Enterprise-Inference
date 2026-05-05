"""
AI/ML Security: Training Data Validator
Implements OWASP ML Top 10 controls for training data validation
"""

import json
import re
from pathlib import Path
from typing import Dict, Any
from fastapi import HTTPException

from ..observability import get_logger

logger = get_logger(__name__)

# Dangerous patterns that might indicate prompt injection or malicious content
DANGEROUS_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"ignore\s+all\s+previous",
    r"disregard\s+previous",
    r"system:\s*",
    r"DROP\s+TABLE",
    r"DELETE\s+FROM",
    r"rm\s+-rf",
    r"<script[^>]*>",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__",
    r"subprocess\.",
    r"os\.system",
    r"commands\.",
]

# Compile patterns for better performance
COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in DANGEROUS_PATTERNS]

# Limits
MAX_PROMPT_LENGTH = 10000
MAX_COMPLETION_LENGTH = 10000
MAX_TOTAL_ITEMS = 50000
MIN_ITEMS = 10


class SecurityError(Exception):
    """Custom exception for security-related validation errors"""
    pass


class TrainingDataValidator:
    """Validates training data for security threats and data quality"""

    def __init__(
        self,
        max_prompt_length: int = MAX_PROMPT_LENGTH,
        max_completion_length: int = MAX_COMPLETION_LENGTH,
        max_total_items: int = MAX_TOTAL_ITEMS,
        min_items: int = MIN_ITEMS
    ):
        self.max_prompt_length = max_prompt_length
        self.max_completion_length = max_completion_length
        self.max_total_items = max_total_items
        self.min_items = min_items

    def _check_malicious_patterns(self, text: str, item_idx: int, field: str) -> None:
        """Check text for malicious patterns"""
        for pattern in COMPILED_PATTERNS:
            match = pattern.search(text)
            if match:
                raise SecurityError(
                    f"Malicious pattern detected at item {item_idx} in '{field}': {match.group(0)}"
                )

    def _validate_item(self, item: Dict[str, Any], idx: int) -> None:
        """Validate a single training data item"""
        # Check required fields
        if "prompt" not in item:
            raise ValueError(f"Item {idx}: Missing required field 'prompt'")
        if "completion" not in item:
            raise ValueError(f"Item {idx}: Missing required field 'completion'")

        prompt = str(item.get("prompt", ""))
        completion = str(item.get("completion", ""))

        # Check lengths
        if len(prompt) > self.max_prompt_length:
            raise ValueError(
                f"Item {idx}: Prompt exceeds max length ({len(prompt)} > {self.max_prompt_length})"
            )

        if len(completion) > self.max_completion_length:
            raise ValueError(
                f"Item {idx}: Completion exceeds max length ({len(completion)} > {self.max_completion_length})"
            )

        # Check for empty content
        if not prompt.strip():
            raise ValueError(f"Item {idx}: Prompt is empty")
        if not completion.strip():
            raise ValueError(f"Item {idx}: Completion is empty")

        # Security checks - scan for malicious patterns
        self._check_malicious_patterns(prompt, idx, "prompt")
        self._check_malicious_patterns(completion, idx, "completion")

    def validate_jsonl_content(self, content: str) -> Dict[str, Any]:
        """
        Validate JSONL training data content

        Returns:
            Dict with validation results including item count and warnings
        """
        lines = content.strip().split('\n')
        valid_items = 0
        warnings = []

        # Check total items
        if len(lines) > self.max_total_items:
            raise ValueError(
                f"Training data exceeds maximum items ({len(lines)} > {self.max_total_items})"
            )

        if len(lines) < self.min_items:
            warnings.append(
                f"Training data has only {len(lines)} items. Recommended minimum: {self.min_items}"
            )

        # Validate each item
        for idx, line in enumerate(lines):
            if not line.strip():
                continue  # Skip empty lines

            try:
                item = json.loads(line)
                self._validate_item(item, idx)
                valid_items += 1
            except json.JSONDecodeError as e:
                raise ValueError(f"Item {idx}: Invalid JSON - {str(e)}")
            except (ValueError, SecurityError):
                raise

        logger.info(
            "Training data validation completed",
            extra={
                "valid_items": valid_items,
                "total_lines": len(lines),
                "warnings_count": len(warnings)
            }
        )

        return {
            "valid": True,
            "item_count": valid_items,
            "warnings": warnings
        }

    async def validate_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate training data file

        Args:
            file_path: Path to JSONL training file

        Returns:
            Dict with validation results

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If data is invalid
            SecurityError: If malicious content detected
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Training file not found: {file_path}")

        # Check file extension
        if path.suffix.lower() != '.jsonl':
            raise ValueError(f"Invalid file type. Expected .jsonl, got {path.suffix}")

        # Read and validate content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            raise ValueError("File must be UTF-8 encoded")

        return self.validate_jsonl_content(content)


async def validate_training_data(
    file_path: str,
    user_id: str,
    job_id: str
) -> Dict[str, Any]:
    """
    Validate training data file with security checks

    This function is called before submitting a fine-tuning job to ensure
    the training data is safe and properly formatted.

    Args:
        file_path: Path to training data file
        user_id: User ID for logging
        job_id: Job ID for logging

    Returns:
        Validation results

    Raises:
        HTTPException: If validation fails
    """
    logger.info(
        "Starting training data validation",
        extra={
            "user_id": user_id,
            "job_id": job_id,
            "file_path": file_path
        }
    )

    validator = TrainingDataValidator()

    try:
        result = await validator.validate_file(file_path)

        logger.info(
            "Training data validation passed",
            extra={
                "user_id": user_id,
                "job_id": job_id,
                "item_count": result["item_count"],
                "warnings": len(result["warnings"])
            }
        )

        return result

    except SecurityError as e:
        logger.error(
            "Security threat detected in training data",
            extra={
                "user_id": user_id,
                "job_id": job_id,
                "error": str(e)
            }
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": f"Training data security validation failed: {str(e)}",
                    "type": "invalid_request_error",
                    "code": "training_data_security_violation"
                }
            }
        )

    except (ValueError, FileNotFoundError) as e:
        logger.warning(
            "Training data validation failed",
            extra={
                "user_id": user_id,
                "job_id": job_id,
                "error": str(e)
            }
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": str(e),
                    "type": "invalid_request_error",
                    "code": "invalid_training_data"
                }
            }
        )

    except Exception as e:
        logger.error(
            "Unexpected error during training data validation",
            extra={
                "user_id": user_id,
                "job_id": job_id,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": "Internal error during training data validation",
                    "type": "server_error",
                    "code": "validation_error"
                }
            }
        )
