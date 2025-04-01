# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Configuration module for Waldiez runner."""

from ._common import ENV_PREFIX, FALSY, ROOT_DIR, TRUTHY, in_container
from ._redis import RedisScheme
from ._server import ServerStatus
from .settings import Settings
from .settings_manager import SettingsManager

MAX_ACTIVE_TASKS = 50
MAX_CLIENTS_PER_TASK = 5

__all__ = [
    "RedisScheme",
    "ServerStatus",
    "Settings",
    "SettingsManager",
    "ENV_PREFIX",
    "ROOT_DIR",
    "TRUTHY",
    "FALSY",
    "in_container",
    "MAX_ACTIVE_TASKS",
    "MAX_CLIENTS_PER_TASK",
]
