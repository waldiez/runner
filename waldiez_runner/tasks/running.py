# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught, unused-argument
"""Handle running tasks."""

import logging
import os
import shutil
import tempfile
from pathlib import Path

from aiofiles.os import wrap
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqDepends

from waldiez_runner.config import SettingsManager
from waldiez_runner.dependencies import RedisManager, Storage
from waldiez_runner.models.task_status import TaskStatus
from waldiez_runner.schemas.task import TaskResponse
from waldiez_runner.services import TaskService

from .__base__ import broker
from .dependencies import get_db_session, get_redis_manager, get_storage
from .runner import execute_task, prepare_app_env

LOG = logging.getLogger(__name__)
HERE = Path(__file__).parent
APP_DIR = HERE / "app"


@broker.task
async def run_task(
    task: TaskResponse,
    db_session: AsyncSession = TaskiqDepends(get_db_session),
    storage: Storage = TaskiqDepends(get_storage),
    redis_manager: RedisManager = TaskiqDepends(get_redis_manager),
) -> None:
    """Run a new triggered task.

    Parameters
    ----------
    task: Task
        Task object.
    db_session : AsyncSession
        Database session dependency.
    storage : Storage
        Storage backend dependency.
    redis_manager : RedisManager
        Redis connection manager dependency.

    Raises
    ------
    RuntimeError
        If the task could not be executed.
    """
    temp_dir = Path(tempfile.mkdtemp())
    venv_dir = await prepare_app_env(storage, task, temp_dir)
    app_dir = temp_dir / task.client_id / task.id / "app"
    file_path = temp_dir / task.client_id / task.id / "app" / task.filename
    settings = SettingsManager.load_settings()
    debug = settings.log_level.upper() == "DEBUG"
    async with (
        # redis_manager.contextual_client(True) as redis_pub,
        redis_manager.contextual_client(True) as redis_sub,
    ):
        status, results = await execute_task(
            task,
            venv_dir,
            app_dir,
            file_path,
            redis_url=redis_manager.redis_url,
            redis_sub=redis_sub,
            db_session=db_session,
            debug=debug,
        )
        LOG.info("Task %s finished with status %s", task.id, status.value)
        LOG.debug("Task %s finished with results %s", task.id, results)
        if status != TaskStatus.COMPLETED and results is not None:
            try:
                await TaskService.update_task_status(
                    session=db_session,
                    task_id=task.id,
                    status=status,
                    results=results,
                )
            except BaseException as e:
                raise RuntimeError(
                    "Failed to update task status in the database"
                ) from e
        await move_results_to_storage(temp_dir, task, storage)


async def move_results_to_storage(
    temp_dir: Path,
    task: TaskResponse,
    storage: Storage,
) -> None:
    """Copy the results to the storage.

    Parameters
    ----------
    temp_dir : Path
        Temporary directory.
    task: TaskResponse
        TaskResponse object.
    storage : Storage
        Storage backend dependency.

    Raises
    ------
    RuntimeError
        If the results could not be copied to the storage.
    """
    # results_dir = os.path.join(temp_dir, task_dir, "app")
    results_dir = temp_dir / task.client_id / task.id / "app" / "waldiez_out"
    if not results_dir.exists():
        LOG.warning("No results directory found for task %s", task.id)
        return
    # Copy results to storage
    results_dir_dst = os.path.join(task.client_id, task.id, "waldiez_out")
    try:
        await storage.copy_folder(str(results_dir), results_dir_dst)
    except BaseException as e:
        LOG.error("Failed to copy results to storage: %s", e)
        raise RuntimeError("Failed to copy results to storage") from e
    # Remove temporary directory
    rmtree = wrap(shutil.rmtree)
    try:
        await rmtree(str(temp_dir), ignore_errors=True)
    except FileNotFoundError:
        LOG.warning("Temporary directory %s not found", temp_dir)
    except PermissionError:
        LOG.warning(
            "Permission denied to remove temporary directory %s", temp_dir
        )
