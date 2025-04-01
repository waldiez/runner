# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught, unused-argument
"""Handle running tasks."""

import asyncio
import logging
import os
import shutil
import subprocess  # nosemgrep # nosec
import tempfile
import venv
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqDepends

from waldiez_runner.dependencies import AsyncRedis, Storage
from waldiez_runner.models import TaskResponse, TaskStatus
from waldiez_runner.services import TaskService

from .common import broker, redis_status_key
from .dependencies import get_db_session, get_redis, get_redis_url, get_storage

LOG = logging.getLogger(__name__)
HERE = Path(__file__).parent
APP_DIR = HERE / "app"


async def _update_task_status(
    task_id: str,
    new_status: TaskStatus,
    db_session: AsyncSession,
    redis: AsyncRedis,
) -> None:
    """Update the task status.

    Parameters
    ----------
    task_id : str
        Task ID.
    new_status : TaskStatus
        New task status.
    db_session : AsyncSession
        Database session dependency.
    redis : AsyncRedis
        Redis dependency.

    Raises
    ------
    RuntimeError
        If the task status could not be updated.
    """
    try:
        await TaskService.update_task_status(
            session=db_session, task_id=task_id, new_status=new_status
        )
    except BaseException as e:
        raise RuntimeError(
            "Failed to update task status in the database"
        ) from e
    try:
        await redis.set(redis_status_key(task_id), new_status.value)
    except BaseException as e:
        if getattr(broker, "_is_smoke_testing", False) is True:
            return
        LOG.error("Failed to update task status in Redis: %s", e)
        raise RuntimeError("Failed to update task status in Redis") from e


async def _get_redis_status(redis: AsyncRedis, task_id: str) -> str:
    """Get the task status from Redis.

    Parameters
    ----------
    redis : AsyncRedis
        Redis dependency.
    task_id : str
        Task ID.

    Returns
    -------
    str
        Task status.

    Raises
    ------
    RuntimeError
        If the task status could not be retrieved.
    """
    status = TaskStatus.RUNNING.value
    try:
        status_fetched = await redis.get(redis_status_key(task_id))
    except BaseException as e:
        if getattr(broker, "_is_smoke_testing", False) is True:
            return status
        LOG.error("Failed to get task status from Redis: %s", e)
        raise RuntimeError("Failed to get task status from Redis") from e
    status = (
        str(status_fetched)
        if status_fetched is not None and not isinstance(status_fetched, str)
        else status
    )
    return status


@broker.task
async def run_task(
    task: TaskResponse,
    db_session: AsyncSession = TaskiqDepends(get_db_session),
    storage: Storage = TaskiqDepends(get_storage),
    redis: AsyncRedis = TaskiqDepends(get_redis),
    redis_url: str = TaskiqDepends(get_redis_url),
) -> None:
    """Trigger a new task.

    Parameters
    ----------
    task: Task
        Task object.
    db_session : AsyncSession
        Database session dependency.
    storage : Storage
        Storage backend dependency.
    redis : AsyncRedis
        Redis dependency.
    redis_url : str
        Redis URL dependency.
    """
    temp_dir = Path(tempfile.mkdtemp())
    venv_dir = await prepare_app_env(storage, task, temp_dir)
    app_dir = temp_dir / task.client_id / task.id / "app"
    try:
        await _update_task_status(
            task.id, TaskStatus.RUNNING, db_session, redis
        )
    except BaseException as e:
        LOG.error("Failed to update task status: %s", e)
        return
    # pylint: disable=too-many-try-statements
    file_path = temp_dir / task.client_id / task.id / "app" / task.filename
    try:
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            None,
            run_app_in_venv,
            venv_dir,
            app_dir,
            task.id,
            file_path,
            redis_url,
            task.input_timeout,
        )
        while not future.done():
            await asyncio.sleep(1)
            try:
                status = await _get_redis_status(redis, task.id)
            except BaseException as e:
                LOG.error("Failed to get task status: %s", e)
                return
            if status.upper() == "CANCELLED":
                LOG.info("Cancelling task %s via Redis control", task.id)
                future.cancel()
                await TaskService.update_task_status(
                    session=db_session,
                    task_id=task.id,
                    new_status=TaskStatus.CANCELLED,
                )
                return

        exit_code = await future
        new_status = (
            TaskStatus.COMPLETED if exit_code == 0 else TaskStatus.FAILED
        )
        await _update_task_status(task.id, new_status, db_session, redis)
    except asyncio.CancelledError:
        await _update_task_status(
            task.id, TaskStatus.CANCELLED, db_session, redis
        )
    except BaseException as e:
        LOG.error("Task %s failed: %s", task.id, e)
        await redis.set(redis_status_key(task.id), TaskStatus.FAILED.value)
        await TaskService.update_task_status(
            session=db_session, task_id=task.id, new_status=TaskStatus.FAILED
        )
    finally:
        # TODO: copy the results to the storage
        await copy_results_to_storage(temp_dir, task, storage)
        shutil.rmtree(temp_dir)
    LOG.debug("Task %s completed", task.id)


def get_venv_python_executable(venv_root: Path) -> Path:
    """Get the Python executable in the venv.

    Parameters
    ----------
    venv_root : Path
        Venv root directory.

    Returns
    -------
    Path
        Python executable.
    """
    if os.name == "nt":  # pragma: no cover
        return venv_root / "Scripts" / "python.exe"
    # on mac, this could be python3?
    py3_path = venv_root / "bin" / "python3"
    if py3_path.exists():
        return py3_path
    return venv_root / "bin" / "python"


async def prepare_app_env(
    storage: Storage, task: TaskResponse, storage_root: Path
) -> Path:
    """Prepare the app environment.

    Parameters
    ----------
    storage : Storage
        Storage backend dependency.
    task: TaskResponse
        TaskResponse object.
    storage_root : Path
        Storage root directory.

    Returns
    -------
    Path
        Venv directory.
    """
    task_dir = storage_root / task.client_id / task.id
    task_file_src = os.path.join(task.client_id, task.id, task.filename)
    app_dir = task_dir / "app"
    venv_dir = task_dir / "venv"

    os.makedirs(app_dir, exist_ok=True)

    # Create venv
    venv.create(venv_dir, with_pip=True, system_site_packages=True)

    # Copy app
    if app_dir.exists():
        shutil.rmtree(app_dir)
    shutil.copytree(APP_DIR, app_dir, dirs_exist_ok=True)
    await storage.copy_file(task_file_src, str(app_dir / task.filename))
    # Install dependencies
    python_exec = get_venv_python_executable(venv_dir)
    subprocess.run(
        [str(python_exec), "-m", "pip", "install", "-r", "requirements.txt"],
        check=True,
        cwd=app_dir,
    )

    return venv_dir


def run_app_in_venv(
    venv_root: Path,
    app_dir: Path,
    task_id: str,
    file_path: Path,
    redis_url: str,
    input_timeout: int,
) -> int:
    """Run the app in the venv.

    Parameters
    ----------
    venv_root : Path
        Venv root directory.
    app_dir : Path
        App directory.
    redis_url : str
        Redis URL.
    task_id : str
        Task ID.
    file_path : Path
        Path to the task file.
    input_timeout : int
        Input timeout.
    Returns
    -------
    int
        Exit code.
    """
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    python_exec = get_venv_python_executable(venv_root)
    module_name = "main"

    # pylint: disable=consider-using-with
    process = subprocess.Popen(
        [
            str(python_exec),
            "-m",
            module_name,
            "--task-id",
            task_id,
            "--redis-url",
            redis_url,
            "--input-timeout",
            str(input_timeout),
            str(file_path),
        ],
        cwd=app_dir,
        env=env,
    )

    return process.wait()


async def copy_results_to_storage(
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
    """
