# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""WebSocket route utilities."""

from .dependency import (
    validate_websocket_connection,
    ws_task_registry,
)
from .task_manager import WsTaskManager
from .task_registry import WsTaskRegistry

__all__ = [
    "WsTaskManager",
    "WsTaskRegistry",
    "validate_websocket_connection",
    "ws_task_registry",
]
