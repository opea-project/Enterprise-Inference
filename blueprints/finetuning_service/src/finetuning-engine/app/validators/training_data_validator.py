# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
OWASP ML Top 10 – ML01: Input Manipulation / Training Data Poisoning.

Validates training data files before they are passed to the fine-tuning
engine.  Enforces:
  - File format: only .jsonl allowed.
  - Size constraints on individual records.
  - A scan for 9 well-known malicious / prompt-injection patterns.
  - A base-model allowlist so only approved foundation models can be used.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import List

logger = logging.getLogger("uvicorn")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 9 malicious patterns (OWASP ML Top 10 / prompt-injection catalogue)
MALICIOUS_PATTERNS: List[str] = [
    "ignore previous instructions",
    "system:",
    "DROP TABLE",
    "rm -rf",
    "<script>",
    "eval(",
    "os.system",
    "exec(",
    "__import__",
]

# Only JSONL training files are accepted
ALLOWED_EXTENSIONS = {".jsonl"}

# Approved base models for fine-tuning
ALLOWED_BASE_MODELS = {
    "meta-llama/Llama-3.2-3B-Instruct",
    "meta-llama/Llama-3.1-8B-Instruct",
}

# Maximum length (chars) for a single prompt / completion field
MAX_FIELD_LENGTH = 32_768  # 32 k chars


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TrainingDataValidationError(ValueError):
    """Raised when training data fails security validation."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_model_allowlist(model_name: str) -> None:
    """
    Raise TrainingDataValidationError if *model_name* is not on the
    approved base-model allowlist.
    """
    if model_name not in ALLOWED_BASE_MODELS:
        logger.warning(
            f"[ML-SECURITY] Rejected model not on allowlist: '{model_name}'"
        )
        raise TrainingDataValidationError(
            f"Model '{model_name}' is not on the approved base-model allowlist. "
            f"Approved models: {sorted(ALLOWED_BASE_MODELS)}"
        )
    logger.info(f"[ML-SECURITY] Base model validated: '{model_name}'")


def validate_training_file(file_path: str) -> None:
    """
    Validate a training data file.

    Checks performed (in order):
    1. Extension must be .jsonl.
    2. File must be non-empty.
    3. Each line must be valid JSON.
    4. Each record is scanned for malicious patterns.
    5. Field lengths are bounded.

    Args:
        file_path: Absolute path to the downloaded JSONL file.

    Raises:
        TrainingDataValidationError: on any security or format violation.
        FileNotFoundError: if the file does not exist.
    """
    path = Path(file_path)

    # --- 1. Extension check ------------------------------------------------
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise TrainingDataValidationError(
            f"Invalid file extension '{path.suffix}'. "
            f"Only {ALLOWED_EXTENSIONS} files are accepted."
        )

    # --- 2. Non-empty check ------------------------------------------------
    if not path.exists():
        raise FileNotFoundError(f"Training file not found: {file_path}")

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise TrainingDataValidationError("Training file is empty.")

    logger.info(
        f"[ML-SECURITY] Starting validation of '{path.name}' "
        f"({file_size / 1024:.1f} KB)"
    )

    # --- 3 + 4 + 5. Line-by-line validation --------------------------------
    compiled_patterns = [
        re.compile(re.escape(p), re.IGNORECASE) for p in MALICIOUS_PATTERNS
    ]

    with open(file_path, encoding="utf-8", errors="replace") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            raw_line = raw_line.rstrip("\n")
            if not raw_line:
                continue  # skip blank lines

            # --- Valid JSON? ------------------------------------------------
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise TrainingDataValidationError(
                    f"Invalid JSON on line {lineno}: {exc}"
                ) from exc

            # --- Collect text fields for scanning --------------------------
            text_fields = _extract_text_fields(record, lineno)

            for field_name, text in text_fields:
                # Length check
                if len(text) > MAX_FIELD_LENGTH:
                    raise TrainingDataValidationError(
                        f"Line {lineno}, field '{field_name}' exceeds maximum "
                        f"length ({len(text)} > {MAX_FIELD_LENGTH} chars)."
                    )

                # Malicious pattern scan
                for pattern, compiled in zip(MALICIOUS_PATTERNS, compiled_patterns):
                    if compiled.search(text):
                        logger.error(
                            f"[ML-SECURITY] Malicious pattern detected at "
                            f"line {lineno}, field '{field_name}': '{pattern}'"
                        )
                        raise TrainingDataValidationError(
                            f"Malicious pattern detected at line {lineno} "
                            f"(field '{field_name}'): '{pattern}'. "
                            "Training data rejected."
                        )

    logger.info(
        f"[ML-SECURITY] Validation passed for '{path.name}' "
        f"({lineno} records scanned)."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_text_fields(record: dict | list | str, lineno: int) -> list[tuple[str, str]]:
    """
    Recursively extract all string values from a JSON record so that both
    standard Alpaca-style {instruction/input/output} and chat-style
    {messages: [{role, content}]} formats are covered.
    """
    results: list[tuple[str, str]] = []

    if isinstance(record, str):
        results.append(("value", record))
    elif isinstance(record, list):
        for i, item in enumerate(record):
            results.extend(_extract_text_fields(item, lineno))
    elif isinstance(record, dict):
        for key, value in record.items():
            if isinstance(value, str):
                results.append((key, value))
            else:
                results.extend(_extract_text_fields(value, lineno))
    return results
