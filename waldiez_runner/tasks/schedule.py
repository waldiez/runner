# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught
"""Task scheduled tasks."""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi_pagination import Page, Params
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqDepends
from typing_extensions import Annotated

from waldiez_runner.config import Settings
from waldiez_runner.dependencies import DatabaseManager, RedisManager, Storage
from waldiez_runner.models import Task, TaskStatus
from waldiez_runner.services import TaskService

from .__base__ import broker
from .app.redis_io_stream import RedisIOStream
from .dependencies import (
    get_db_manager,
    get_redis_manager,
    get_settings,
    get_storage,
)

LOG = logging.getLogger(__name__)

OLD_DELETED_TASKS_ARE_DELETED_AFTER = 30  # days


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
async def cleanup_old_deleted_tasks(
    db_manager: Annotated[DatabaseManager, TaskiqDepends(get_db_manager)],
    storage: Annotated[Storage, TaskiqDepends(get_storage)],
) -> None:
    """Periodic cleanup of old tasks marked for deletion.

    Parameters
    ----------
    storage : Storage
        Storage backend.
    db_manager : DatabaseManager
        Database session manager.
    """
    async with db_manager.session() as session:
        await _purge_tasks(
            db_session=session,
            storage=storage,
            days_before=OLD_DELETED_TASKS_ARE_DELETED_AFTER,
            deleted=True,
        )


@broker.task
async def cleanup_old_tasks(
    db_manager: Annotated[DatabaseManager, TaskiqDepends(get_db_manager)],
    storage: Annotated[Storage, TaskiqDepends(get_storage)],
    settings: Annotated[Settings, TaskiqDepends(get_settings)],
) -> None:
    """Cleanup tasks created before the configured number of days.

    Parameters
    ----------
    storage : Storage
        Storage backend.
    db_manager : DatabaseManager
        Database session manager.
    settings: Settings
        The settings instance.
    """
    days_before = settings.keep_task_for_days
    if days_before > 0:
        async with db_manager.session() as session:
            await _purge_tasks(
                db_session=session,
                storage=storage,
                deleted=False,
                days_before=days_before,
            )


async def _purge_tasks(
    db_session: AsyncSession,
    storage: Storage,
    deleted: bool,
    days_before: int,
    max_concurrency: int = 8,
    batch_size: int = 100,
) -> None:
    """Purge tasks."""
    sem = asyncio.Semaphore(max_concurrency)
    total_deleted = 0
    older_than = datetime.now(timezone.utc) - timedelta(days=days_before)
    repeats = 0
    max_loops = 10_000
    while repeats < max_loops:
        repeats += 1
        rows = await TaskService.get_old_tasks(
            db_session,
            older_than=older_than,
            deleted=deleted,
            batch_size=batch_size,
        )
        if not rows:
            break

        task_ids: list[str] = [r[0] for r in rows]
        await TaskService.delete_tasks(db_session, task_ids=task_ids)

        async def _rm(client_id: str, task_id: str) -> None:
            async with sem:
                try:
                    await storage.delete_folder(
                        os.path.join(client_id, str(task_id))
                    )
                except BaseException as e:  # pragma: no cover
                    LOG.error("Error deleting task storage: %s", e)

        # client_id (row[1]), task.id (row[0])
        await asyncio.gather(*(_rm(row[1], row[0]) for row in rows))
        total_deleted += len(rows)
    LOG.info("Cleaned up %s old tasks.", total_deleted)


@broker.task
async def check_stuck_tasks(
    db_manager: Annotated[DatabaseManager, TaskiqDepends(get_db_manager)],
    storage: Annotated[Storage, TaskiqDepends(get_storage)],
) -> None:
    """Task to check tasks that are marked as active but have results.

    Parameters
    ----------
    db_manager : DatabaseManager
        Database session manager dependency.
    storage : Storage
        Storage implementation dependency.
    """
    stuck_tasks: list[Task] = []
    page = 1
    while page < 50:
        params = Params(page=page, size=100)
        async with db_manager.session() as db_session:
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
        async with db_manager.session() as db_session:
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
