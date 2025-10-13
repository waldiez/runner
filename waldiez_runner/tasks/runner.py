# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught, unused-argument
"""Handle running the task in a virtual environment."""

import asyncio
import contextlib
import logging
import os
import shutil
import signal
import sys
import traceback
import venv
from pathlib import Path
from typing import Any

import aiofiles
from aiofiles.os import wrap

from waldiez_runner.dependencies import AsyncRedis, DatabaseManager, Storage
from waldiez_runner.models.task_status import TaskStatus
from waldiez_runner.schemas.task import TaskResponse
from waldiez_runner.services import TaskService

from .__base__ import APP_DIR
from .status_watcher import terminate_process, watch_status_and_cancel_if_needed

LOG = logging.getLogger(__name__)


async def execute_task(
    task: TaskResponse,
    env_vars: dict[str, str],
    venv_dir: Path,
    app_dir: Path,
    file_path: Path,
    redis_url: str,
    redis_sub: AsyncRedis,
    db_manager: DatabaseManager,
    debug: bool,
    max_duration: int,
) -> tuple[TaskStatus, dict[str, Any] | list[dict[str, Any]] | None]:
    """Execute the task in a virtual environment.

    Parameters
    ----------
    task : TaskResponse
        TaskResponse object.
    env_vars : dict[str, str]
        Environment variables for the task.
    venv_dir : Path
        Venv directory.
    app_dir : Path
        App directory.
    file_path : Path
        Path to the task file.
    redis_url : str
        Redis URL.
    redis_sub : AsyncRedis
        Dedicated Redis client for subscribing to task status.
    db_manager : DatabaseManager
        Database session manager dependency.
    debug : bool
        Whether to run in debug mode.
    max_duration : int
        The task's max duration.

    Returns
    -------
    tuple[TaskStatus, dict | list[dict] | None]
        The derived task status and optional results.
    """
    # pylint: disable=broad-exception-caught
    try:
        exit_code = await run_app_in_venv(
            venv_root=venv_dir,
            env_vars=env_vars,
            app_dir=app_dir,
            task_id=task.id,
            file_path=file_path,
            redis_url=redis_url,
            input_timeout=task.input_timeout,
            redis_sub=redis_sub,
            db_manager=db_manager,
            debug=debug,
            max_duration=max_duration,
        )
        LOG.info("Task %s exited with code %s", task.id, exit_code)
        return interpret_exit_code(exit_code)

    except asyncio.CancelledError:
        return TaskStatus.CANCELLED, {"error": "Task cancelled"}

    except BaseException as e:
        LOG.exception("Task %s failed unexpectedly", task.id)
        return TaskStatus.FAILED, {"error": str(e)}


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
    storage: Storage,
    task: TaskResponse,
    storage_root: Path,
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
        # noinspection PyBroadException
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
    pip_args = [
        "install",
        "--upgrade-strategy",
        "only-if-needed",
        "-r",
        "requirements.txt",
    ]
    await run_pip(python_exec, app_dir, pip_args)
    return venv_dir


def _pip_env() -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        "PIP_NO_INPUT": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }


async def run_pip(
    python_exec: Path,
    cwd: Path,
    args: list[str],
    *,
    timeout: float | None = None,
    extra_env: dict[str, str] | None = None,
) -> None:
    """Run pip in the venv.

    Parameters
    ----------
    python_exec : Path
        Python executable in the venv.
    cwd : Path
        Current working directory.
    args : list[str]
        Arguments to pass to pip.
    timeout : float | None
        Optional timeout for the operation.
    extra_env : dict[str, str] | None
        Optional additional environment variables.

    Raises
    ------
    RuntimeError
        If pip installation fails.
    """
    env = _pip_env()
    if extra_env:
        env.update(extra_env)
    proc = await asyncio.create_subprocess_exec(
        str(python_exec),
        "-m",
        "pip",
        *args,
        cwd=cwd,
        env=env,
    )
    try:
        if timeout and timeout > 0:
            rc = await asyncio.wait_for(proc.wait(), timeout=timeout)
        else:
            rc = await proc.wait()
    except asyncio.TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        raise RuntimeError(f"pip timed out with args: {args}") from None

    if rc != 0:
        raise RuntimeError(f"pip failed (exit {rc}) with args: {args}")


# pylint: disable=too-many-locals
async def run_app_in_venv(
    venv_root: Path,
    env_vars: dict[str, str],
    app_dir: Path,
    task_id: str,
    file_path: Path,
    redis_url: str,
    input_timeout: int,
    redis_sub: AsyncRedis,
    db_manager: DatabaseManager,
    debug: bool,
    max_duration: int,
) -> int:
    """Run the app in the venv.

    Parameters
    ----------
    venv_root : Path
        Venv root directory.
    env_vars : dict[str, str]
        Environment variables for the task.
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
    db_manager : DatabaseManager
        Database session manager dependency.
    debug : bool
        Whether to run in debug mode.
    max_duration : int
        The task's max duration.

    Returns
    -------
    int
        Exit code.
    """
    python_exec = get_venv_python_executable(venv_root)
    await write_dot_env(app_dir, env_vars)
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
    async with db_manager.session() as db_session:
        await TaskService.trigger(
            db_session,
            task_id=task_id,
        )
    watcher_task = asyncio.create_task(
        watch_status_and_cancel_if_needed(
            task_id=task_id,
            process=process,
            redis=redis_sub,
            db_manager=db_manager,
        )
    )
    # pylint: disable=too-many-try-statements
    try:
        if max_duration > 0:
            return_code = await asyncio.wait_for(
                process.wait(), timeout=max_duration
            )
        else:
            return_code = await process.wait()

        if watcher_task.done():
            try:
                watcher_result = watcher_task.result()
                if watcher_result is not None:
                    LOG.warning(
                        "Watcher task finished with result: %s", watcher_result
                    )
                    return_code = watcher_result
            except Exception as e:
                LOG.debug(traceback.format_exc())
                LOG.warning("Watcher task error: %s", e)
                return_code = -1
        return return_code
    except asyncio.TimeoutError:
        LOG.warning(
            "Task %s exceeded max duration of %s seconds", task_id, max_duration
        )
        await terminate_process(process)
        return -99
    finally:
        if not watcher_task.done():
            watcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher_task


# pylint: disable=too-many-return-statements
def interpret_exit_code(
    exit_code: int,
) -> tuple[TaskStatus, dict[str, Any] | None]:
    """Interpret subprocess exit code.

    Parameters
    ----------
    exit_code : int
        The return code from `await process.wait()`.

    Returns
    -------
    tuple[TaskStatus, dict | None]
        The derived task status and optional results.
    """
    if exit_code == 0:
        return TaskStatus.COMPLETED, None
    if exit_code == -99:
        return TaskStatus.FAILED, {"error": "Task duration exceeded its limit."}
    if exit_code == -signal.SIGTERM:
        return TaskStatus.CANCELLED, {"error": "Task was terminated by signal"}
    # Unix: process terminated by signal (Python reports it as -N)
    if exit_code < 0:
        return TaskStatus.CANCELLED, {
            "error": f"Terminated by signal {-exit_code}"
        }

    # Windows: specific exit codes for termination
    if sys.platform == "win32":  # pragma: no cover
        # Ctrl+C or task kill: 0xC000013A → 3221225786
        if exit_code in (0xC000013A, 3221225786):
            return TaskStatus.CANCELLED, {
                "error": "Cancelled via Ctrl+C or task kill (Windows)"
            }
        # Could check for more patterns here if needed
        return TaskStatus.FAILED, {
            "error": f"Task failed with exit code {exit_code}"
        }

    # Fallback: exit code suggests failure
    return TaskStatus.FAILED, {
        "error": f"Task failed with exit code {exit_code}"
    }


async def write_dot_env(app_dir: Path, env_vars: dict[str, str]) -> None:
    """Write environment variables to a .env file in the app directory.

    Parameters
    ----------
    app_dir : Path
        App directory.
    env_vars : dict[str, str]
        Environment variables to write.
    """
    dot_env_path = app_dir / ".env"
    async with aiofiles.open(
        dot_env_path, "w", encoding="utf-8", newline="\n"
    ) as f_out:
        for key, value in env_vars.items():
            await f_out.write(f"{key}={value}\n")
    LOG.debug("Wrote environment variables to %s", dot_env_path)
