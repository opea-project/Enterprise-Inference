# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Shared slowapi rate-limiter instance.

Import this module in main.py to register the exception handler, and in
routers to apply per-endpoint limits via the @limiter.limit() decorator.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared limiter; key_func identifies clients by their remote IP address
limiter = Limiter(key_func=get_remote_address)
