"""
Extraction utility modules.

Provides coverage calculation and validation utilities for extraction quality assessment.
"""

from .coverage import calculate_field_coverage, validate_field_types

__all__ = ['calculate_field_coverage', 'validate_field_types']
