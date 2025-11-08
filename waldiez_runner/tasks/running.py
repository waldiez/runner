# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught, unused-argument
# pyright: reportCallInDefaultInitializer=false
"""Handle running tasks."""

import logging
import os
import shutil
import tempfile
from pathlib import Path

from aiofiles.os import wrap
from taskiq import TaskiqDepends

from waldiez_runner.config import SettingsManager
from waldiez_runner.dependencies import DatabaseManager, RedisManager, Storage
from waldiez_runner.models.task_status import TaskStatus
from waldiez_runner.schemas.task import TaskResponse
from waldiez_runner.services import TaskService

from .__base__ import broker
from .dependencies import get_db_manager, get_redis_manager, get_storage
from .runner import execute_task, prepare_app_env

LOG = logging.getLogger(__name__)
HERE = Path(__file__).parent
APP_DIR = HERE / "app"


# pylint: disable=too-many-locals
@broker.task
async def run_task(
    task: TaskResponse,
    env_vars: dict[str, str],
    db_manager: DatabaseManager = TaskiqDepends(get_db_manager),
    storage: Storage = TaskiqDepends(get_storage),
    redis_manager: RedisManager = TaskiqDepends(get_redis_manager),
) -> None:
    """Run a new triggered task.

    Parameters
    ----------
    task: Task
        Task object.
    env_vars: dict[str, str]
        Environment variables for the task.
    db_manager : DatabaseManager
        Database session manager dependency.
    storage : Storage
        Storage backend dependency.
    redis_manager : RedisManager
        Redis connection manager dependency.

    Raises
    ------
    RuntimeError
        If the task could not be executed.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="wlz-brk"))
    try:
        venv_dir = await prepare_app_env(storage, task, temp_dir)
    except BaseException as error:
        LOG.error("Failed to prepare the app env: %s", error)
        async with db_manager.session() as db_session:
            await TaskService.update_task_status(
                session=db_session,
                task_id=task.id,
                status=TaskStatus.FAILED,
                results=[{"error": str(error)}],
            )
        await remove_tmp_dir(temp_dir=temp_dir)
        return
    app_dir = temp_dir / task.client_id / task.id / "app"
    file_path = temp_dir / task.client_id / task.id / "app" / task.filename
    settings = SettingsManager.load_settings()
    debug = settings.log_level.upper() == "DEBUG"
    async with (
        # redis_manager.contextual_client(True) as redis_pub,
        redis_manager.contextual_client(
            use_single_connection=True
        ) as redis_sub,
    ):
        status, results = await execute_task(
            task,
            env_vars,
            venv_dir,
            app_dir,
            file_path,
            redis_url=redis_manager.redis_url,
            redis_sub=redis_sub,
            db_manager=db_manager,
            debug=debug,
            max_duration=settings.max_task_duration,
        )
        LOG.info("Task %s finished with status %s", task.id, status.value)
        LOG.debug("Task %s finished with results %s", task.id, results)
        if status != TaskStatus.COMPLETED and results is not None:
            try:
                async with db_manager.session() as db_session:
                    await TaskService.update_task_status(
                        session=db_session,
                        task_id=task.id,
                        status=status,
                        results=results,
                    )
            except BaseException as e:
                await remove_tmp_dir(temp_dir=temp_dir)
                raise RuntimeError(
                    "Failed to update task status in the database"
                ) from e
    if settings.keep_task_for_days > 0:
        await copy_results_to_storage(
            app_dir=app_dir,
            task=task,
            storage=storage,
        )
    await remove_tmp_dir(temp_dir=temp_dir)


async def copy_results_to_storage(
    app_dir: Path,
    task: TaskResponse,
    storage: Storage,
) -> None:
    """Copy the results to the storage.

    Parameters
    ----------
    app_dir : Path
        Temporary directory with the app.
    task: TaskResponse
        TaskResponse object.
    storage : Storage
        Storage backend dependency.

    Raises
    ------
    RuntimeError
        If the results could not be copied to the storage.
    """
    results_dir = app_dir / "waldiez_out"
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
    dst_dot_env = os.path.join(task.client_id, task.id, "app", ".env")
    if await storage.is_file(dst_dot_env):
        await storage.delete_file(dst_dot_env)


async def remove_tmp_dir(temp_dir: Path) -> None:
    """Remove task's temporary directory.

    Parameters
    ----------
    temp_dir : Path
        The temp dir to remove.
    """
    if not temp_dir.is_dir():
        LOG.warning("Not a directory: %s", temp_dir)
        return
    rmtree = wrap(shutil.rmtree)
    try:
        await rmtree(str(temp_dir), ignore_errors=True)
        LOG.debug("Removed temporary directory: %s", temp_dir)
    except FileNotFoundError:
        LOG.warning("Temporary directory %s not found", temp_dir)
    except PermissionError:
        LOG.warning(
            "Permission denied to remove temporary directory %s", temp_dir
        )
    except BaseException as err:
        LOG.warning("Unexpected error: %s", err)
