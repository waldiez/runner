# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Application state and lifecycle management."""

import logging

from waldiez_runner.config import Settings, SettingsManager
from waldiez_runner.services import TaskService

from .database import DatabaseManager
from .jwks import JWKSCache
from .redis import RedisManager
from .storage import StorageBackend

LOG = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
class AppState:
    """Global application state."""

    settings: Settings | None = None
    db: DatabaseManager | None = None
    redis: RedisManager | None = None
    jwks_cache: JWKSCache | None = None
    storage_backend: StorageBackend | None = None


app_state = AppState()


async def on_startup() -> None:
    """Configure the application."""
    # force reload once to get the final settings from env
    settings = SettingsManager.load_settings(force_reload=True)
    app_state.settings = settings
    app_state.db = DatabaseManager(settings)
    app_state.redis = RedisManager(settings)
    app_state.jwks_cache = JWKSCache(settings)
    # if we add more backends, we can add a setting for this
    # and use the one from the settings
    app_state.storage_backend = "local"


async def on_shutdown() -> None:
    """Close the application."""
    # pylint: disable=broad-exception-caught
    if app_state.db is not None:
        try:
            async with app_state.db.session() as session:
                await TaskService.mark_active_tasks_as_failed(session)
        except BaseException as e:  # pragma: no cover
            LOG.error("Error marking tasks as failed: %s", e)
        try:
            await app_state.db.close()
        except BaseException as e:  # pragma: no cover
            LOG.error("Error closing database: %s", e)
    if app_state.redis is not None:
        try:
            await app_state.redis.close()
        except BaseException as e:  # pragma: no cover
            LOG.error("Error closing Redis client: %s", e)
