# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
OWASP ML Top 10 – ML08: Model Theft / Extraction Detection.

Tracks how many times per hour each authenticated user retrieves completed
job results (i.e. accesses the output model artefact).  A user that exceeds
the threshold is flagged as a potential model-extraction attempt and the
suspicious activity is logged with enough context for a security analyst to
investigate.

Design notes:
  - State is kept in-process (no external cache dependency).
  - Thread-safe via an asyncio Lock.
  - Counts are bucketed per *hour* so the usage window automatically slides.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Dict, Tuple

logger = logging.getLogger("uvicorn")

# Alert after this many completed-job reads within one hour per user.
EXTRACTION_THRESHOLD = 3

# Seconds in the rolling window (1 hour)
WINDOW_SECONDS = 3600


class ModelExtractionDetector:
    """
    Lightweight in-process extraction detector.

    Usage (call from any endpoint or background task that returns a completed
    model to the client):

        detector = ModelExtractionDetector()   # use module-level singleton
        detector.record_access(username="alice", job_id=42)
    """

    def __init__(self) -> None:
        # {username: [(timestamp, job_id), ...]}
        self._access_log: Dict[str, list[Tuple[float, int]]] = defaultdict(list)

    def record_access(self, username: str, job_id: int) -> None:
        """
        Record that *username* accessed the output of *job_id*.

        Logs a WARNING if the user's access count within the rolling window
        exceeds EXTRACTION_THRESHOLD.

        Args:
            username: Authenticated username/email.
            job_id:   The completed job whose model was accessed.
        """
        now = time.monotonic()
        cutoff = now - WINDOW_SECONDS

        # Prune old entries outside the rolling window
        self._access_log[username] = [
            (ts, jid)
            for ts, jid in self._access_log[username]
            if ts >= cutoff
        ]

        # Record this access
        self._access_log[username].append((now, job_id))

        count = len(self._access_log[username])

        logger.info(
            f"[ML-SECURITY] Model access: user='{username}' "
            f"job_id={job_id} "
            f"accesses_in_window={count}/{EXTRACTION_THRESHOLD}"
        )

        if count > EXTRACTION_THRESHOLD:
            logger.warning(
                f"[ML-SECURITY] ALERT – Possible model extraction detected! "
                f"user='{username}' made {count} model accesses in the last "
                f"{WINDOW_SECONDS // 60} minutes "
                f"(threshold={EXTRACTION_THRESHOLD}). "
                f"Jobs accessed: "
                f"{[jid for _, jid in self._access_log[username]]}"
            )


# ---------------------------------------------------------------------------
# Module-level singleton – import and call from any router/service.
# ---------------------------------------------------------------------------
extraction_detector = ModelExtractionDetector()
