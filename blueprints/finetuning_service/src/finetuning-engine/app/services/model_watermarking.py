# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
OWASP ML Top 10 – ML06: Model Integrity.

Writes cryptographic provenance metadata (watermark) into the model output
directory so that ownership and lineage can be audited later.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("uvicorn")

# Name of the metadata sidecar file written next to model artefacts
WATERMARK_FILENAME = "model_provenance.json"


def watermark_model(
    output_dir: str,
    job_id: int,
    username: str,
    model_name: str,
) -> dict:
    """
    Write a provenance (watermark) JSON file inside *output_dir*.

    The file records:
      - owner (username)
      - job id
      - base model used
      - UTC timestamp
      - a SHA-256 fingerprint of ``<job_id>:<username>:<model_name>``

    Args:
        output_dir: Directory where the fine-tuned model artefacts reside.
        job_id:     Numeric job identifier.
        username:   Username / email of the job submitter.
        model_name: HuggingFace base-model handle used for fine-tuning.

    Returns:
        The provenance dict that was written to disk.

    Raises:
        OSError: if the output directory does not exist or is not writable.
    """
    path = Path(output_dir)
    if not path.exists():
        raise OSError(f"Model output directory does not exist: {output_dir}")

    # Build deterministic fingerprint
    fingerprint_input = f"{job_id}:{username}:{model_name}"
    fingerprint = hashlib.sha256(fingerprint_input.encode()).hexdigest()

    provenance = {
        "version": "1.0",
        "job_id": job_id,
        "owner": username,
        "base_model": model_name,
        "watermarked_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": fingerprint,
        "fingerprint_algorithm": "SHA-256",
        "fingerprint_input": f"job_id:username:model_name (SHA-256)",
    }

    watermark_path = path / WATERMARK_FILENAME
    with open(watermark_path, "w", encoding="utf-8") as fh:
        json.dump(provenance, fh, indent=2)

    logger.info(
        f"[ML-SECURITY] Model watermark written to '{watermark_path}' "
        f"(fingerprint: {fingerprint[:16]}...)"
    )
    return provenance
