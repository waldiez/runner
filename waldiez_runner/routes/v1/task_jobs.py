# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pylint: disable=too-many-lines
# pyright: reportPossiblyUnboundVariable=false, reportUnusedParameter=false

"""Task router helpers."""

import asyncio
import logging

from waldiez_runner.dependencies import DatabaseManager, Storage, app_state
from waldiez_runner.schemas.task import TaskResponse
from waldiez_runner.tasks import broker
from waldiez_runner.tasks import delete_task as delete_task_job
from waldiez_runner.tasks import run_task as run_task_job

LOG = logging.getLogger(__name__)


async def trigger_run_task(
    task: TaskResponse,
    db_manager: DatabaseManager,
    storage: Storage,
    env_vars: dict[str, str],
) -> None:
    """Trigger a task.

    Parameters
    ----------
    task : TaskResponse
        The task to trigger.
    db_manager : DatabaseManager
        The db session manager dependency.
    storage : Storage
        The storage dependency.
    env_vars : dict[str,str]
        The environment variables for the task

    Raises
    ------
    RuntimeError
        If Redis is not initialized.
    """
    if not app_state.redis:  # pragma: no cover
        raise RuntimeError("Redis not initialized")
    if getattr(broker, "_is_smoke_testing", False) is True:  # pragma: no cover
        LOG.warning("Using fake Redis, running task in background")
        bg_task = asyncio.create_task(
            run_task_job(
                task=task,
                env_vars=env_vars,
                db_manager=db_manager,
                storage=storage,
                redis_manager=app_state.redis,
            )
        )
        bg_task.add_done_callback(
            lambda t: (
                LOG.exception("run_task_job failed", exc_info=t.exception())
                if t.exception()
                else LOG.info("run_task_job succeeded")
            )
        )
    else:
        await run_task_job.kiq(task=task, env_vars=env_vars)


async def trigger_delete_task(
    task_id: str,
    client_id: str,
    db_manager: DatabaseManager,
    storage: Storage,
) -> None:
    """Trigger a task deletion.

    Parameters
    ----------
    task_id : str
        The task's id
    client_id : str
        The client id that triggered the action.
    db_manager : DatabaseManager
        The db session manager dependency.
    storage : Storage
        The storage dependency.
    """
    if getattr(broker, "_is_smoke_testing", False) is True:
        LOG.warning("Using fake Redis, deleting task in background")
        bg_task = asyncio.create_task(
            delete_task_job(
                task_id=task_id,
                client_id=client_id,
                db_manager=db_manager,
                storage=storage,
            )
        )
        bg_task.add_done_callback(
            lambda t: (
                LOG.exception("delete_task_job failed", exc_info=t.exception())
                if t.exception()
                else LOG.info("delete_task_job succeeded")
            )
        )
    else:  # pragma: no cover
        await delete_task_job.kiq(
            task_id=task_id,
            client_id=client_id,
        )


# pylint: disable=unused-argument
async def schedule_task(
    task: TaskResponse,
    db_manager: DatabaseManager,
    storage: Storage,
    env_vars: dict[str, str],
) -> None:
    """Schedule a task.

    Parameters
    ----------
    task : TaskResponse
        The task to schedule.
    db_manager : DatabaseManager
        The database session manager.
    storage : Storage
        The storage service.
    env_vars : dict[str, str]
        The environment variables for the task.

    Raises
    ------
    NotImplementedError
        Not implemented
    """
    LOG.debug(
        "Scheduling task %s with schedule type %s",
        task.id,
        task.schedule_type,
    )
    msg = (
        "Scheduling tasks is not implemented yet. "
        "Please check the documentation for updates."
    )
    raise NotImplementedError(msg)
