# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Common utilities for storage services."""

ALLOWED_EXTENSIONS = (".waldiez",)
ALLOWED_MIME_TYPES = ("application/json", "application/text", "text/plain")

CHUNK_SIZE = 1024 * 1024  # 1 MB
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
