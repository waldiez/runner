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
import venv
from pathlib import Path
from typing import Any, Dict, List, Tuple

from aiofiles.os import wrap
from sqlalchemy.ext.asyncio import AsyncSession

from waldiez_runner.dependencies import AsyncRedis, Storage
from waldiez_runner.models.task_status import TaskStatus
from waldiez_runner.schemas.task import TaskResponse

from .__base__ import APP_DIR
from .status_watcher import watch_status_and_cancel_if_needed

LOG = logging.getLogger(__name__)


async def execute_task(
    task: TaskResponse,
    venv_dir: Path,
    app_dir: Path,
    file_path: Path,
    redis_url: str,
    redis_sub: AsyncRedis,
    db_session: AsyncSession,
    debug: bool,
) -> Tuple[TaskStatus, Dict[str, Any] | List[Dict[str, Any]] | None]:
    """Execute the task in a virtual environment.

    Parameters
    ----------
    task : TaskResponse
        TaskResponse object.
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
    db_session : AsyncSession
        Database session dependency.
    debug : bool
        Whether to run in debug mode.

    Returns
    -------
    Tuple[TaskStatus, dict | list[dict] | None]
        The derived task status and optional results.
    """
    # pylint: disable=broad-exception-caught
    try:
        exit_code = await run_app_in_venv(
            venv_root=venv_dir,
            app_dir=app_dir,
            task_id=task.id,
            file_path=file_path,
            redis_url=redis_url,
            input_timeout=task.input_timeout,
            redis_sub=redis_sub,
            db_session=db_session,
            debug=debug,
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
    await run_pip(python_exec, app_dir, ["install", "--upgrade", "pip"])
    await run_pip(python_exec, app_dir, ["install", "-r", "requirements.txt"])

    return venv_dir


async def run_pip(python_exec: Path, cwd: Path, args: List[str]) -> None:
    """Run pip in the venv.

    Parameters
    ----------
    python_exec : Path
        Python executable in the venv.
    cwd : Path
        Current working directory.
    args : List[str]
        Arguments to pass to pip.

    Raises
    ------
    RuntimeError
        If pip installation fails.
    """
    proc = await asyncio.create_subprocess_exec(
        str(python_exec),
        "-m",
        "pip",
        *args,
        cwd=cwd,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    if await proc.wait() != 0:
        raise RuntimeError(f"Failed to run pip with args: {args}")


# pylint: disable=too-many-locals
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
        watch_status_and_cancel_if_needed(
            task_id=task_id,
            process=process,
            redis=redis_sub,
            db_session=db_session,
        )
    )
    # pylint: disable=too-many-try-statements
    try:
        return_code = await process.wait()

        if watcher_task.done():
            try:
                watcher_result = watcher_task.result()
                if watcher_result is not None:  # pyright: ignore
                    LOG.warning(
                        "Watcher task finished with result: %s", watcher_result
                    )
                    return_code = watcher_result
            except Exception as e:
                LOG.warning("Watcher task error: %s", e)
                return_code = -1

        return return_code
    finally:
        if not watcher_task.done():
            watcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher_task


def interpret_exit_code(
    exit_code: int,
) -> Tuple[TaskStatus, Dict[str, Any] | None]:
    """Interpret subprocess exit code in a cross-platform way.

    Parameters
    ----------
    exit_code : int
        The return code from `await process.wait()`.

    Returns
    -------
    Tuple[TaskStatus, dict | None]
        The derived task status and optional results.
    """
    if exit_code == 0:
        return TaskStatus.COMPLETED, None
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
