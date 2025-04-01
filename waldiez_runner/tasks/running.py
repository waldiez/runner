# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught, unused-argument
"""Handle running tasks."""

import asyncio
import logging
import os
import shutil
import tempfile
import venv
from pathlib import Path
from typing import Any, Dict, List

from aiofiles.os import wrap
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
            task.id,
            TaskStatus.RUNNING,
            db_session,
            redis,
            results=None,
        )
    except BaseException as e:
        LOG.error("Failed to update task status: %s", e)
        return
    # pylint: disable=too-many-try-statements
    file_path = temp_dir / task.client_id / task.id / "app" / task.filename
    # loop = asyncio.get_event_loop()
    try:
        future = asyncio.create_task(
            run_app_in_venv(
                venv_dir,
                app_dir,
                task.id,
                file_path,
                redis_url,
                task.input_timeout,
            )
        )
        await _check_task_status(
            task=task,
            future=future,
            db_session=db_session,
            redis=redis,
        )
        exit_code = await future
        await _handle_task_completion(
            exit_code,
            task=task,
            db_session=db_session,
            redis=redis,
        )
    except asyncio.CancelledError:
        await _update_task_status(
            task.id,
            TaskStatus.CANCELLED,
            db_session,
            redis,
            results={"error": "Task cancelled"},
        )
    except BaseException as e:
        LOG.error("Task %s failed: %s", task.id, e)
        await redis.set(
            redis_status_key(task.id), TaskStatus.FAILED.value, ex=60
        )
        await TaskService.update_task_status(
            session=db_session,
            task_id=task.id,
            status=TaskStatus.FAILED,
            results={"error": str(e)},
        )
    finally:
        await move_results_to_storage(temp_dir, task, storage)
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

    Raises
    ------
    RuntimeError
        If the app environment could not be prepared.
    """
    task_dir = storage_root / task.client_id / task.id
    task_file_src = os.path.join(task.client_id, task.id, task.filename)
    app_dir = task_dir / "app"
    venv_dir = task_dir / "venv"
    # Create venv
    venv.create(venv_dir, with_pip=True, system_site_packages=True)

    # Copy app
    if app_dir.exists():
        rmtree = wrap(shutil.rmtree)
        try:
            await rmtree(str(app_dir), ignore_errors=True)
        except BaseException:
            LOG.warning("Failed to remove existing app directory %s", app_dir)
    copytree = wrap(shutil.copytree)
    try:
        await copytree(str(APP_DIR), str(app_dir), dirs_exist_ok=True)
    except BaseException as err:
        LOG.warning("Failed to copy app directory %s", app_dir)
        raise RuntimeError("Failed to copy app directory") from err
    await storage.copy_file(task_file_src, str(app_dir / task.filename))
    # Install dependencies
    python_exec = get_venv_python_executable(venv_dir)
    async_proc = await asyncio.create_subprocess_exec(
        str(python_exec),
        "-m",
        "pip",
        "install",
        "--upgrade",
        "pip",
        cwd=app_dir,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    if await async_proc.wait() != 0:
        raise RuntimeError("Failed to upgrade pip")
    # Install requirements
    async_proc = await asyncio.create_subprocess_exec(
        str(python_exec),
        "-m",
        "pip",
        "install",
        "-r",
        "requirements.txt",
        cwd=app_dir,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    if await async_proc.wait() != 0:
        raise RuntimeError("Failed to install requirements")
    return venv_dir


async def run_app_in_venv(
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
    python_exec = get_venv_python_executable(venv_root)
    module_name = "main"

    process = await asyncio.create_subprocess_exec(
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
        cwd=app_dir,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    return await process.wait()


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


async def _check_task_status(
    task: TaskResponse,
    future: asyncio.Task[int],
    db_session: AsyncSession,
    redis: AsyncRedis,
) -> None:
    while not future.done():
        await asyncio.sleep(1)

        try:
            status = await _get_redis_status(redis, task.id)
        except BaseException as e:
            LOG.error("Failed to get task status for %s: %s", task.id, e)
            return

        status_upper = status.upper()

        if status_upper == "CANCELLED":
            LOG.info("Task %s was cancelled via Redis", task.id)
            await _handle_status_update(
                future,
                db_session,
                task.id,
                TaskStatus.CANCELLED,
                "Task cancelled",
            )
            return

        if status_upper == "FAILED":
            LOG.warning("Task %s marked as FAILED in Redis", task.id)
            await _handle_status_update(
                future, db_session, task.id, TaskStatus.FAILED, "Task failed"
            )
            return

        if status_upper in ("RUNNING", "WAITING_FOR_INPUT", "PENDING"):
            LOG.debug("Task %s is in progress: %s", task.id, status_upper)
            continue

        # Unexpected status
        LOG.warning("Unexpected task status for %s: '%s'", task.id, status)
        await _handle_status_update(
            future,
            db_session,
            task.id,
            TaskStatus.FAILED,
            f"Unexpected status: {status}",
        )
        return


async def _handle_status_update(
    future: asyncio.Future[int],
    db_session: AsyncSession,
    task_id: str,
    status: TaskStatus,
    error_message: str,
) -> None:
    _cancel_future_if_running(future)
    await TaskService.update_task_status(
        session=db_session,
        task_id=task_id,
        status=status,
        results={"error": error_message},
    )


def _cancel_future_if_running(future: asyncio.Future[int]) -> None:
    """Cancel the future if it is running.

    Parameters
    ----------
    future : asyncio.Future[int]
        Future object.
    """
    if not future.cancelled() and not future.done():
        future.cancel()


async def _handle_task_completion(
    exit_code: int,
    task: TaskResponse,
    db_session: AsyncSession,
    redis: AsyncRedis,
) -> None:
    status = await _get_redis_status(redis, task.id)
    if exit_code != 0 and status not in (
        TaskStatus.CANCELLED.value,
        TaskStatus.FAILED.value,
    ):
        LOG.error("Task %s failed with exit code %s", task.id, exit_code)
        await TaskService.update_task_status(
            session=db_session,
            task_id=task.id,
            status=TaskStatus.FAILED,
            results={"error": "Task failed"},
        )
        return
    task_status: TaskStatus = TaskStatus(status)
    if getattr(broker, "_is_smoke_testing", False) is True:
        task_status = (
            TaskStatus.COMPLETED if exit_code == 0 else TaskStatus.FAILED
        )
    # TODO: get the results from redis (tasks:{task.id}:results)
    await _update_task_status(
        task.id,
        task_status,
        db_session,
        redis,
        {"exit_code": exit_code},
    )


async def _update_task_status(
    task_id: str,
    new_status: TaskStatus,
    db_session: AsyncSession,
    redis: AsyncRedis,
    results: Dict[str, Any] | List[Dict[str, Any]] | None,
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
            session=db_session,
            task_id=task_id,
            status=new_status,
            results=results,
        )
    except BaseException as e:
        raise RuntimeError(
            "Failed to update task status in the database"
        ) from e
    try:
        await redis.set(redis_status_key(task_id), new_status.value, ex=60)
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
    if isinstance(status_fetched, bytes):
        status = status_fetched.decode()
    elif isinstance(status_fetched, str):
        status = status_fetched
    else:
        LOG.warning(
            "Unexpected task status type from Redis: %s", type(status_fetched)
        )
        return status
    try:
        TaskStatus(status.upper())
    except ValueError:
        LOG.warning("Unexpected task status from Redis: %s", status)
        status = TaskStatus.RUNNING.value
    return status
