# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught
"""Task scheduled tasks."""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi_pagination import Page, Params
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqDepends
from typing_extensions import Annotated

from waldiez_runner.dependencies import RedisManager, Storage
from waldiez_runner.models import Task, TaskStatus
from waldiez_runner.services import TaskService

from .__base__ import broker
from .app.redis_io_stream import RedisIOStream
from .dependencies import get_db_session, get_redis_manager, get_storage

LOG = logging.getLogger(__name__)

OLD_TASKS_ARE_DELETED_AFTER = 30  # days


# @broker.task(schedule=EVERY_5_MINUTES)
@broker.task
async def heartbeat() -> None:
    """Periodic heartbeat."""
    # just a log message for now
    # in the future we might want to report our status to an external service.
    # e.g. if we are in a polling mode,
    # we can do this here.
    # a simple log for now is ok
    # to check if the taskiq worker is alive
    # and the scheduling is working
    LOG.info("Heartbeat")


@broker.task
async def cleanup_processed_requests(
    redis_manager: Annotated[RedisManager, TaskiqDepends(get_redis_manager)],
) -> None:
    """Periodic cleanup of stale processed requests.

    Parameters
    ----------
    redis_manager : RedisManager
        Redis connection manager.
    """
    async with redis_manager.contextual_client(
        use_single_connection=True
    ) as redis:
        await RedisIOStream.a_cleanup_processed_requests(
            redis,
            retention_period=86400,  # 86400 seconds = 1 day
        )
        LOG.info("Cleaned up stale processed requests.")


@broker.task
async def cleanup_old_tasks(
    db_session: Annotated[AsyncSession, TaskiqDepends(get_db_session)],
    storage: Annotated[Storage, TaskiqDepends(get_storage)],
) -> None:
    """Periodic cleanup of old tasks.

    Parameters
    ----------
    storage : Storage
        Storage backend.
    db_session : AsyncSession
        Database session.
    """
    page = 1
    old_tasks: List[Task] = []
    while page < 100:
        params = Params(page=page, size=100)
        tasks: Page[Task] = await TaskService.get_tasks_to_delete(
            db_session,
            older_than=datetime.now(timezone.utc)
            - timedelta(days=OLD_TASKS_ARE_DELETED_AFTER),
            params=params,
        )
        if not tasks.items:
            break
        old_tasks.extend(tasks.items)
        page += 1
    for task in old_tasks:
        await delete_old_task_from_db(db_session, task)
        await delete_old_task_from_storage(storage, task)
    LOG.info("Cleaned up old tasks.")


@broker.task
async def check_stuck_tasks(
    db_session: Annotated[AsyncSession, TaskiqDepends(get_db_session)],
    storage: Annotated[Storage, TaskiqDepends(get_storage)],
) -> None:
    """Task to check tasks that are marked as active but have results.

    Parameters
    ----------
    db_session : AsyncSession
        Database session dependency.
    storage : Storage
        Storage implementation dependency.
    """
    stuck_tasks: List[Task] = []
    page = 1
    while page < 50:
        params = Params(page=page, size=100)
        tasks: Page[Task] = await TaskService.get_stuck_tasks(
            db_session,
            params=params,
        )
        if not tasks.items:
            break
        stuck_tasks.extend(tasks.items)
        page += 1
    for task in stuck_tasks:
        new_status = await check_stuck_task_status(task, storage)
        await TaskService.update_task_status(
            db_session,
            task_id=task.id,
            status=new_status,
            skip_results=True,
        )
    LOG.info("Checked stuck tasks.")


@broker.task
async def trim_old_stream_entries(
    redis_manager: Annotated[RedisManager, TaskiqDepends(get_redis_manager)],
    maxlen: int = 1000,
    scan_count: int = 100,
) -> None:
    """Periodic cleanup of old stream entries.

    Parameters
    ----------
    redis_manager : RedisManager
        Redis connection manager.
    maxlen : int, optional
        The maximum length of the stream, by default 1000.
    scan_count : int, optional
        The number of entries to scan at a time, by default 100.
    """
    async with redis_manager.contextual_client(
        use_single_connection=True
    ) as redis:
        await RedisIOStream.a_trim_task_output_streams(
            redis,
            maxlen=maxlen,
            scan_count=scan_count,
        )


async def delete_old_task_from_db(
    db_session: AsyncSession,
    task: Task,
) -> None:
    """Delete an old task from the database.

    Parameters
    ----------
    db_session : AsyncSession
        Database session dependency.
    task : Task
        The task to delete.
    """
    try:
        await TaskService.delete_task(db_session, task_id=task.id)
    except BaseException as e:  # pragma: no cover
        LOG.error("Error deleting task: %s", e)


async def delete_old_task_from_storage(
    storage: Storage,
    task: Task,
) -> None:
    """Delete an old task from the storage backend.

    Parameters
    ----------
    storage : Storage
        Storage backend dependency.
    task : Task
        The task to delete.
    """
    try:
        await storage.delete_folder(os.path.join(task.client_id, str(task.id)))
    except BaseException as e:  # pragma: no cover
        LOG.error("Error deleting task storage: %s", e)


async def check_stuck_task_status(task: Task, storage: Storage) -> TaskStatus:
    """Check the status of a task.

    Parameters
    ----------
    task : Task
        The task to check.
    storage : Storage
        The storage backend instance to use.

    Returns
    -------
    TaskStatus
        The status of the task.
    """
    if task.results is None:
        return TaskStatus.FAILED
    if isinstance(task.results, dict) and "error" in task.results:
        return TaskStatus.FAILED
    try:
        files = await storage.list_files(
            os.path.join(task.client_id, str(task.id))
        )
    except BaseException as e:  # pragma: no cover
        LOG.error(
            "Error while checking task status for task %s: %s",
            task.id,
            e,
        )
        return TaskStatus.FAILED
    if not files:
        return TaskStatus.FAILED
    return TaskStatus.COMPLETED
