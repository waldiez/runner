# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Taskiq dependencies setup."""

import logging
from collections.abc import AsyncGenerator

from taskiq import Context, TaskiqDepends
from typing_extensions import Annotated

from waldiez_runner.config import Settings
from waldiez_runner.dependencies import (
    DatabaseManager,
    RedisManager,
    Storage,
    get_storage_backend,
)

LOG = logging.getLogger(__name__)


async def get_db_manager(
    context: Annotated[Context, TaskiqDepends()],
) -> AsyncGenerator[DatabaseManager, None]:
    """Get the database session.

    Parameters
    ----------
    context : Context
        Taskiq context.

    Yields
    ------
    AsyncSession
        The database session.

    Raises
    ------
    RuntimeError
        If the database is not initialized.
    """
    if not context.state.db or not context.state.db.engine:  # pragma: no cover
        raise RuntimeError("Database not initialized")
    yield context.state.db


async def get_settings(
    context: Annotated[Context, TaskiqDepends()],
) -> Settings:
    """Get the Redis client.

    Parameters
    ----------
    context : Context
        Taskiq context.

    Returns
    -------
    Settings
        The settings.
    """
    return context.state.settings


async def get_redis_manager(
    context: Annotated[Context, TaskiqDepends()],
) -> RedisManager:
    """Get the Redis client.

    Parameters
    ----------
    context : Context
        Taskiq context.

    Returns
    -------
    RedisManager
        The Redis manager instance.
    """
    return context.state.redis_manager


def get_storage(
    context: Annotated[Context, TaskiqDepends()],
) -> Storage:
    """Get the storage backend.

    Parameters
    ----------
    context : Context
        Taskiq context.

    Returns
    -------
    Storage
        The storage backend implementation.
    """
    return get_storage_backend(context.state.storage)
