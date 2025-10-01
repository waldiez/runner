# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Password hashing and verification."""

from .dispatcher import PasswordHasherDispatcher
from .protocol import Hasher

password_hasher: Hasher = PasswordHasherDispatcher()

__all__ = ["password_hasher", "Hasher"]
