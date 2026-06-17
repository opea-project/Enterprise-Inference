"""
Field coverage scoring for extraction quality assessment.

Evaluates extraction completeness to determine pipeline stage progression.
"""

import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


def calculate_field_coverage(
    extracted_data: Dict[str, Any],
    schema: Dict[str, Any]
) -> Tuple[float, Dict[str, bool]]:
    """
    Calculate field coverage percentage based on schema requirements.

    Args:
        extracted_data: Extracted field values
        schema: Schema definition with required fields

    Returns:
        Tuple of (coverage_percentage, field_status_map)
            coverage_percentage: Percentage of required fields successfully extracted (0.0-1.0)
            field_status_map: Dict mapping field names to extraction success boolean
    """
    if not schema:
        return 1.0, {}

    total_required = 0
    extracted_required = 0
    field_status = {}

    for field_name, field_def in schema.items():
        is_required = True
        if isinstance(field_def, dict):
            is_required = field_def.get('required', True)

        if is_required:
            total_required += 1
            value = extracted_data.get(field_name)
            is_extracted = value is not None and value != ""

            if is_extracted:
                extracted_required += 1
                field_status[field_name] = True
            else:
                field_status[field_name] = False
        else:
            value = extracted_data.get(field_name)
            field_status[field_name] = value is not None and value != ""

    coverage = extracted_required / total_required if total_required > 0 else 1.0

    logger.debug(
        f"Coverage: {coverage:.2%} ({extracted_required}/{total_required} required fields)"
    )

    return coverage, field_status


def validate_field_types(
    extracted_data: Dict[str, Any],
    schema: Dict[str, Any]
) -> Tuple[bool, Dict[str, str]]:
    """
    Validate extracted field values against schema type constraints.

    Args:
        extracted_data: Extracted field values
        schema: Schema definition with field types

    Returns:
        Tuple of (is_valid, validation_errors)
            is_valid: True if all extracted fields match schema types
            validation_errors: Dict mapping field names to error messages
    """
    errors = {}

    for field_name, value in extracted_data.items():
        if value is None:
            continue

        field_def = schema.get(field_name)
        if not field_def:
            continue

        expected_type = field_def.get('type', 'string') if isinstance(field_def, dict) else field_def

        if expected_type == 'number':
            if not isinstance(value, (int, float)):
                errors[field_name] = f"Expected number, got {type(value).__name__}"

        elif expected_type == 'boolean':
            if not isinstance(value, bool):
                errors[field_name] = f"Expected boolean, got {type(value).__name__}"

        elif expected_type == 'date':
            if not isinstance(value, str):
                errors[field_name] = f"Expected date string, got {type(value).__name__}"

        elif expected_type == 'string':
            if not isinstance(value, str):
                errors[field_name] = f"Expected string, got {type(value).__name__}"

        if isinstance(field_def, dict) and 'enum' in field_def:
            allowed_values = field_def['enum']
            if value not in allowed_values:
                errors[field_name] = f"Value '{value}' not in allowed values: {allowed_values}"

    is_valid = len(errors) == 0

    if not is_valid:
        logger.warning(f"Type validation failed: {errors}")

    return is_valid, errors
