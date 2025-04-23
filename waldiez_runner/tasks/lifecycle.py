# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Taskiq worker lifecycle event handlers."""

import logging

from taskiq import TaskiqEvents, TaskiqState

from waldiez_runner.config import SettingsManager
from waldiez_runner.dependencies import (
    REDIS_MANAGER,
    DatabaseManager,
    RedisManager,
    StorageBackend,
)

from .__base__ import broker, scheduler
from .schedule import (
    check_stuck_tasks,
    cleanup_old_tasks,
    cleanup_processed_requests,
    heartbeat,
    trim_old_stream_entries,
)

LOG = logging.getLogger(__name__)

OLD_TASKS_ARE_DELETED_AFTER = 30  # days
EVERY_HOUR = "0 * * * *"
EVERY_DAY = "0 0 * * *"
EVERY_5_MINUTES = "*/5 * * * *"
EVERY_15_MINUTES = "*/15 * * * *"


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def on_worker_startup(state: TaskiqState) -> None:
    """Worker startup event handler.

    Parameters
    ----------
    state : TaskiqState
        Taskiq state.
    """
    settings = SettingsManager.load_settings(force_reload=False)
    db_manager: DatabaseManager = DatabaseManager(settings)
    state.db = db_manager
    if REDIS_MANAGER.is_using_fake_redis():
        LOG.warning("Using fake redis, redis url: %s", REDIS_MANAGER.redis_url)
        state.redis_manager = REDIS_MANAGER
    else:
        redis_manager: RedisManager = RedisManager(settings)
        state.redis_manager = redis_manager
    # storage:
    # if we add more backends, we can add a setting for this
    # and use the one from the settings
    storage_backend: StorageBackend = "local"
    state.storage = storage_backend
    redis_source = scheduler.sources[0]
    # schedule tasks:
    await cleanup_processed_requests.schedule_by_cron(  # type: ignore
        redis_source,
        EVERY_HOUR,
    )
    await cleanup_old_tasks.schedule_by_cron(  # type: ignore
        redis_source,
        EVERY_DAY,
    )
    await check_stuck_tasks.schedule_by_cron(  # type: ignore
        redis_source,
        EVERY_15_MINUTES,
    )
    await trim_old_stream_entries.schedule_by_cron(  # type: ignore
        redis_source,
        EVERY_DAY,
    )
    await heartbeat.schedule_by_cron(
        redis_source,
        EVERY_5_MINUTES,
    )


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def on_worker_shutdown(state: TaskiqState) -> None:
    """Worker shutdown event handler.

    Parameters
    ----------
    state : TaskiqState
        Taskiq state.
    """
    # pylint: disable=broad-exception-caught
    if state.db is not None:
        try:
            await state.db.close()
        except BaseException as e:  # pragma: no cover
            LOG.error("Error closing database: %s", e)
    if state.redis_manager is not None:
        try:
            await state.redis_manager.close()
        except BaseException as e:  # pragma: no cover
            LOG.error("Error closing Redis client: %s", e)
