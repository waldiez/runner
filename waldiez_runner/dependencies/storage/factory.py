# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Storage backend factory."""

from pathlib import Path
from typing import Literal

from .base import Storage
from .local import LocalStorage

LOCAL_STORAGE_ROOT = Path(__file__).parent.parent.parent / "storage"


StorageBackend = Literal["local"]  # to add more here later
"""Supported storage backends."""


def get_storage_backend(
    backend: StorageBackend = "local",
    root_dir: Path = LOCAL_STORAGE_ROOT,
) -> Storage:
    """Get a storage backed.

    Parameters
    ----------
    backend : StorageBackend
        The storage backend provider
    root_dir : Path
        The root directory for the local storage.

    Returns
    -------
    Storage
        The storage backend

    Raises
    ------
    ValueError
        If the backend is not supported.
    """
    if backend == "local":
        return LocalStorage(root_dir)
    raise ValueError(f"Unsupported backend: {backend}")
