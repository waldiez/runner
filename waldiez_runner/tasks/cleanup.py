# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught
"""Cleanup stale tasks."""

import json
import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqDepends

from waldiez_runner.dependencies import AsyncRedis, Storage
from waldiez_runner.models import TaskStatus
from waldiez_runner.services import TaskService

from .common import broker, redis_status_key
from .dependencies import get_db_session, get_redis, get_storage

LOG = logging.getLogger(__name__)


@broker.task
async def delete_task(
    task_id: str,
    client_id: str,
    db_session: AsyncSession = TaskiqDepends(get_db_session),
    storage: Storage = TaskiqDepends(get_storage),
) -> None:
    """Delete a single task.

    Parameters
    ----------
    task_id : str
        The task ID
    client_id : str
        The Client id that triggered the task.
    db_session : AsyncSession
        The database session dependency.
    storage : Storage
        The storage implementation dependency.
    """
    try:
        await TaskService.delete_task(db_session, task_id=task_id)
        LOG.debug("Deleted task %s", task_id)
    except BaseException as exc:
        LOG.error("Error deleting task: %s", exc)
    try:
        await storage.delete_folder(os.path.join(client_id, str(task_id)))
        LOG.debug("Deleted task storage for task %s", task_id)
    except BaseException as exc:
        LOG.error("Error deleting task storage: %s", exc)


@broker.task
async def cancel_task(
    task_id: str,
    client_id: str,
    redis: AsyncRedis = TaskiqDepends(get_redis),
    db_session: AsyncSession = TaskiqDepends(get_db_session),
) -> None:
    """Cancel a task.

    Parameters
    ----------
    task_id : str
        Task ID.
    client_id : str
        Client ID.
    redis : AsyncRedis
        Redis client dependency.
    db_session : AsyncSession
        Database session dependency.
    """
    LOG.debug("Cancelling task %s for client %s", task_id, client_id)
    task_status = {
        "task_id": task_id,
        "status": TaskStatus.CANCELLED.value,
        "data": {"error": "Task Cancelled"},
    }
    await redis.publish(
        json.dumps(task_status),
        redis_status_key(task_id),
    )
    await TaskService.update_task_status(
        db_session,
        task_id,
        status=TaskStatus.CANCELLED,
        results={
            "error": "Task Cancelled",
        },
    )
