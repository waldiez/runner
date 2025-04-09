# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Tasks for the Waldiez runner."""

from .__base__ import broker, get_broker, get_scheduler, scheduler
from .cleanup import delete_task
from .dependencies import get_db_session, get_redis_manager, get_storage
from .lifecycle import on_worker_shutdown, on_worker_startup
from .running import run_task
from .schedule import (
    check_stuck_tasks,
    cleanup_old_tasks,
    cleanup_processed_requests,
)

__all__ = [
    "broker",
    "scheduler",
    "run_task",
    "delete_task",
    "get_broker",
    "get_scheduler",
    "get_db_session",
    "get_redis_manager",
    "get_storage",
    "on_worker_shutdown",
    "on_worker_startup",
    "cleanup_old_tasks",
    "cleanup_processed_requests",
    "check_stuck_tasks",
]
