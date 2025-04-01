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

from .common import broker

LOG = logging.getLogger(__name__)


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
