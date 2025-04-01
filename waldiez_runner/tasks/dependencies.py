# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Taskiq dependencies setup."""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import Context, TaskiqDepends
from typing_extensions import Annotated

from waldiez_runner.dependencies import AsyncRedis, Storage, get_storage_backend
from waldiez_runner.models import Base

LOG = logging.getLogger(__name__)


async def get_db_session(
    context: Annotated[Context, TaskiqDepends()],
) -> AsyncGenerator[AsyncSession, None]:
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
    async with context.state.db.session() as session:
        if context.state.db.is_sqlite:
            # make sure the tables are created
            async with context.state.db.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        yield session


async def get_redis(
    context: Annotated[Context, TaskiqDepends()],
) -> AsyncRedis:
    """Get the Redis client.

    Parameters
    ----------
    context : Context
        Taskiq context.

    Returns
    -------
    AsyncRedis
        The Redis client.
    """
    return await context.state.redis_manager.client()


async def get_redis_url(
    context: Annotated[Context, TaskiqDepends()],
) -> str:
    """Get the Redis URL.

    Parameters
    ----------
    context : Context
        Taskiq context.

    Returns
    -------
    str
        The Redis URL.
    """
    return context.state.redis_manager.redis_url


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
