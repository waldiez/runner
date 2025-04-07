# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught, unused-argument
"""Handle running tasks."""

import asyncio
import contextlib
import json
import logging
import os
import shutil
import signal
import tempfile
import venv
from asyncio.subprocess import Process
from pathlib import Path
from typing import Any, Dict, List, TypedDict

from aiofiles.os import wrap
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqDepends

from waldiez_runner.config import SettingsManager
from waldiez_runner.dependencies import AsyncRedis, RedisManager, Storage
from waldiez_runner.models import TaskResponse, TaskStatus
from waldiez_runner.services import TaskService

from .common import broker, redis_status_key
from .dependencies import get_db_session, get_redis_manager, get_storage

LOG = logging.getLogger(__name__)
HERE = Path(__file__).parent
APP_DIR = HERE / "app"


class ParsedStatus(TypedDict, total=False):
    """Parsed task status message.

    Attributes
    ----------
    status : TaskStatus
        The task status.
    input_request_id : str | None
        The input request ID, if applicable.
    results : dict | list[dict] | None
        The results of the task, if applicable.
    should_terminate : bool
        Whether the task should be terminated.
    """

    status: TaskStatus
    input_request_id: str | None
    results: Dict[str, Any] | List[Dict[str, Any]] | None
    should_terminate: bool


@broker.task
async def run_task(
    task: TaskResponse,
    db_session: AsyncSession = TaskiqDepends(get_db_session),
    storage: Storage = TaskiqDepends(get_storage),
    redis_manager: RedisManager = TaskiqDepends(get_redis_manager),
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
    redis_manager : RedisManager
        Redis connection manager dependency.
    """
    temp_dir = Path(tempfile.mkdtemp())
    venv_dir = await prepare_app_env(storage, task, temp_dir)
    app_dir = temp_dir / task.client_id / task.id / "app"
    file_path = temp_dir / task.client_id / task.id / "app" / task.filename
    settings = SettingsManager.load_settings()
    debug = settings.log_level.upper() == "DEBUG"
    # pylint: disable=too-many-try-statements, broad-exception-caught
    async with (
        redis_manager.contextual_client(True) as redis_pub,
        redis_manager.contextual_client(True) as redis_sub,
    ):
        try:
            exit_code = await run_app_in_venv(
                venv_root=venv_dir,
                app_dir=app_dir,
                task_id=task.id,
                file_path=file_path,
                redis_url=redis_manager.redis_url,
                input_timeout=task.input_timeout,
                redis_sub=redis_sub,
                db_session=db_session,
                debug=debug,
            )
            if exit_code != 0:
                await _update_task_status(
                    task.id,
                    TaskStatus.FAILED,
                    db_session,
                    redis=redis_pub,
                    results={"error": "Task failed"},
                )
                return
        except asyncio.CancelledError:
            await _update_task_status(
                task.id,
                TaskStatus.CANCELLED,
                db_session,
                redis=redis_pub,
                results={"error": "Task cancelled"},
            )
        except BaseException as e:
            LOG.exception("Task %s failed", task.id)
            await redis_pub.publish(
                redis_status_key(task.id), TaskStatus.FAILED.value
            )
            await _update_task_status(
                task.id,
                TaskStatus.FAILED,
                db_session,
                redis=redis_pub,
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
    redis_sub: AsyncRedis,
    db_session: AsyncSession,
    debug: bool,
) -> int:
    """Run the app in the venv.

    Parameters
    ----------
    venv_root : Path
        Venv root directory.
    app_dir : Path
        App directory.
    task_id : str
        Task ID.
    file_path : Path
        Path to the task file.
    redis_url : str
        Redis URL.
    input_timeout : int
        Input timeout.
    redis_sub : AsyncRedis
        Dedicated Redis client for subscribing to task status.
    db_session : AsyncSession
        Database session dependency.
    debug : bool
        Whether to run in debug mode.

    Returns
    -------
    int
        Exit code.
    """
    python_exec = get_venv_python_executable(venv_root)
    args = [
        str(python_exec),
        "-m",
        "main",
        "--task-id",
        task_id,
        "--redis-url",
        redis_url,
        "--input-timeout",
        str(input_timeout),
        str(file_path),
    ]
    if debug:
        args.append("--debug")

    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=app_dir,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        start_new_session=True,
    )

    watcher_task = asyncio.create_task(
        _watch_status_and_cancel_if_needed(
            task_id=task_id,
            process=process,
            redis=redis_sub,
            db_session=db_session,
        )
    )

    try:
        return_code = await process.wait()
        return return_code
    finally:
        # Clean up watcher
        if not watcher_task.done():
            watcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher_task


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


async def _watch_status_and_cancel_if_needed(
    task_id: str,
    process: Process,
    redis: AsyncRedis,
    db_session: AsyncSession,
) -> None:
    channel = f"task:{task_id}:status"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    # pylint: disable=too-many-try-statements
    try:
        async for message in pubsub.listen():
            if process.returncode is not None:
                break  # Process exited

            LOG.debug("Received message: %s", message)
            if (
                not isinstance(message, dict)
                or message.get("type") != "message"
            ):
                LOG.warning("Invalid message type: %s", message.get("type"))
                continue
            parsed = parse_status_message(message.get("data", ""))
            if not parsed:
                continue
            try:
                await TaskService.update_task_status(
                    session=db_session,
                    task_id=task_id,
                    status=parsed["status"],
                    input_request_id=parsed.get("input_request_id"),
                    results=parsed.get("results"),
                )
            except Exception as e:
                LOG.warning("Failed to update task %s in DB: %s", task_id, e)

            if parsed.get("should_terminate"):
                await _terminate_process(process)
                break

            if parsed["status"] in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
                break

    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


def load_redis_message_dict(raw_data: str | bytes) -> Dict[str, Any] | None:
    """Load the message we received from redis.

    Parameters
    ----------
    raw_data: str | bytes
        The raw redis data.

    Returns
    -------
    Dict[str, Any] | None
        The loaded message.
    """
    try:
        message = json.loads(raw_data)
        if isinstance(message, str):
            message = json.loads(message)  # Handle double-encoding
    except BaseException as e:
        LOG.warning("Invalid task status JSON: %s", e)
        return None
    if not isinstance(message, dict):
        return None
    if "data" in message and "status" not in message:
        message = message["data"]
    if isinstance(message, str):  # Handle double-encoding
        try:
            message = json.loads(message)
        except BaseException:
            LOG.warning("Invalid task status JSON: %s", message)
            return None
    if not isinstance(message, dict):
        return None
    return message


def parse_status_message(raw_data: str | bytes) -> ParsedStatus | None:
    """Parses and validates a task status message from Redis.

    Parameters
    ----------
    raw_data : str | bytes
        The raw data received from Redis.
    Returns
    -------
    ParsedStatus | None
        The parsed status message or None if invalid.
    """
    message = load_redis_message_dict(raw_data=raw_data)
    if not message:
        return None
    status_str = message.get("status")
    if not status_str:
        return None
    try:
        status = TaskStatus(status_str)
    except ValueError:
        LOG.warning("Unknown task status: %s", status_str)
        return None

    parsed: ParsedStatus = {"status": status}

    if status == TaskStatus.WAITING_FOR_INPUT:
        parsed["input_request_id"] = message.get("data", {}).get(
            "request_id"
        )  # data: {"request_id": ..., "prompt": ...}
    elif status == TaskStatus.COMPLETED:
        parsed["results"] = message.get("data")
    elif status == TaskStatus.FAILED:
        parsed["results"] = {"error": message.get("data")}
    elif status == TaskStatus.CANCELLED:
        # cast to dict (might be a string)
        error = message.get("data", {"data": message.get("data", "")}).get(
            "data"
        )
        parsed["results"] = {"error": error} if error else None
        parsed["should_terminate"] = True

    return parsed


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
        await redis.publish(redis_status_key(task_id), new_status.value)
    except BaseException as e:
        if getattr(broker, "_is_smoke_testing", False) is True:
            return
        LOG.error("Failed to update task status in Redis: %s", e)
        raise RuntimeError("Failed to update task status in Redis") from e


async def _terminate_process(process: Process) -> None:
    """Terminate the process.

    Parameters
    ----------
    process : Process
        Process object.
    """
    # pylint: disable=no-member
    if process.returncode is not None:
        return
    LOG.info("Terminating process %s", process.pid)
    try:
        if os.name == "nt":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
        except Exception as e:
            LOG.warning("Failed to force kill process: %s", e)
