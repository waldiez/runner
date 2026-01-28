# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.
# pyright: reportPossiblyUnboundVariable=false

"""Task routes."""

import asyncio
import hashlib
import os
import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile
from typing_extensions import Literal
from waldiez import Waldiez

from waldiez_runner.dependencies import (
    ALLOWED_EXTENSIONS,
    DatabaseManager,
    Storage,
    get_filename_from_url,
)
from waldiez_runner.services.task_service import TaskService

from .env_vars import get_env_vars

# MAX_TASKS_PER_CLIENT = 3
# MAX_TASKS_ERROR = (
#     f"Cannot create more than {MAX_TASKS_PER_CLIENT} tasks "
#     "at the same time. Please wait for some tasks to finish"
# )
ALLOWED_REMOTE_URL_SCHEMES = (
    # "http",
    "https",
    # "ftp",
    "ftps",
    "sftp",
    "s3",
    # "gs",
)


async def validate_uploaded_file(
    file: UploadFile, client_id: str, storage: Storage
) -> tuple[str, str, str]:
    """Validate an uploaded file.

    Parameters
    ----------
    file : UploadFile
        The uploaded file.
    client_id : str
        The client id
    storage : Storage
        The storage engine dependency.

    Returns
    -------
    tuple[str, str, str]
        The filename, the file's md5 and the path where the file was saved.

    Raises
    ------
    HTTPException
        If an invalid file was uploaded.
    """
    if not file.filename:  # pragma: no cover
        raise HTTPException(status_code=400, detail="Invalid file")
    if not file.filename.endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Invalid file type")
    file_hash, saved_path = await storage.save_file(client_id, file)
    return file.filename, file_hash, saved_path


async def _validate_file_from_url(
    file_url: str, storage: Storage
) -> tuple[str, str, str]:
    if not file_url.startswith(ALLOWED_REMOTE_URL_SCHEMES):
        raise HTTPException(status_code=400, detail="Invalid file URL")
    filename = get_filename_from_url(
        file_url,
        allowed_extensions=ALLOWED_EXTENSIONS,
        default_extension=ALLOWED_EXTENSIONS[0],
        strict_validation=True,
    )
    file_hash, saved_path = await storage.get_file_from_url(
        file_url=file_url,
    )
    return filename, file_hash, saved_path


async def _validate_file_path(
    client_id: str,
    file_path: str,
    storage: Storage,
) -> tuple[str, str, str]:
    resolved = await storage.resolve(os.path.join(client_id, file_path))
    if not resolved:
        raise HTTPException(status_code=400, detail="Invalid file path")
    saved_path = resolved
    filename = Path(resolved).name
    file_hash = await storage.hash(resolved)
    return filename, file_hash, saved_path


# pylint: disable=too-many-locals
async def validate_task_input(
    db: DatabaseManager,
    file: UploadFile | None,
    file_url: str | None,
    file_path: str | None,
    env_vars: str | None,
    client_id: str,
    storage: Storage,
    max_jobs: int,
    force: bool,
    schedule_type: Literal["once", "cron"] | None = None,
) -> tuple[str, str, str, dict[str, str]]:
    """Validate the uploaded file.

    Parameters
    ----------
    db : DatabaseManager
        The database session manager.
    file : Optional[UploadFile]
        The file to validate.
    file_url : str | None
        The URL of the file to validate, by default None
    file_path : str | None, optional
        The local path of a previously uploaded file to use.
    env_vars : str | None
        A JSON string of environment variables, by default None
    client_id : str
        The client ID.
    storage : Storage
        The storage service.
    max_jobs : int
        The upper limit for concurrent running tasks/jobs (<=0 means no limit)
    force : bool, optional
        Whether to force running even if a task with the same flow has already
        started, by default False
    schedule_type : Optional[Literal["once", "cron"]], optional
        The type of schedule, by default None

    Returns
    -------
    tuple[str, str, str, dict[str, str]]
        The file hash, filename, the saved path, and environment variables.

    Raises
    ------
    HTTPException
        If the file is invalid or
        if the maximum number of tasks per client is reached.
    """
    if schedule_type is not None:
        raise HTTPException(500, detail="Scheduling not supported yet")

    async with db.session() as session:
        active_tasks = await TaskService.get_active_client_tasks(
            session,
            client_id=client_id,
        )
    # pylint: disable=chained-comparison
    if max_jobs > 0 and len(active_tasks.items) >= max_jobs:
        detail = (
            f"Cannot create more than {max_jobs} tasks "
            "at the same time. Please wait for some tasks to finish"
        )
        raise HTTPException(status_code=400, detail=detail)
    saved_path: str = ""
    file_hash: str = ""
    filename: str = ""
    if file:
        filename, file_hash, saved_path = await validate_uploaded_file(
            file, client_id=client_id, storage=storage
        )
    elif file_url:
        filename, file_hash, saved_path = await _validate_file_from_url(
            file_url, storage=storage
        )
    elif file_path:
        filename, file_hash, saved_path = await _validate_file_path(
            client_id=client_id, file_path=file_path, storage=storage
        )
    if not file_hash or not filename or not saved_path:
        raise HTTPException(
            status_code=400,
            detail="Invalid file or file URL",
        )
    filename_hash = hashlib.md5(
        filename.encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:8]
    base_flow_id = f"{file_hash}-{filename_hash}"

    active_task = next(
        (task for task in active_tasks.items if task.flow_id == base_flow_id),
        None,
    )

    if active_task and not force:
        await storage.delete_file(saved_path)
        raise HTTPException(
            status_code=400,
            detail=(
                "A task with the same file already exists. "
                f"Task ID: {active_task.id}, status: {active_task.get_status()}"
            ),
        )

    flow_id = base_flow_id

    if active_task and force:
        # Make this run unique
        nonce = secrets.token_hex(4)
        flow_id = f"{base_flow_id}-{nonce}"

        # File is already saved: move it aside to a unique filename
        new_path = _move_to_random_name(Path(saved_path))
        saved_path = str(new_path)

    environment_vars = get_env_vars(env_vars)
    return flow_id, filename, saved_path, environment_vars


async def validate_waldiez_flow(flow_path: str) -> None:
    """Validate a waldiez file/flow.

    Parameters
    ----------
    flow_path : str
        The path of the flow.

    Raises
    ------
    HTTPException
        If the workflow is invalid.
    """
    try:
        await asyncio.to_thread(Waldiez.load, flow_path)
    except BaseException as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


def _move_exclusive(src: Path, dest_dir: Path, dest_name: str) -> Path:
    """Move src -> dest_dir/dest_name without overwriting anything.

    Safe path allocation:
      - Try atomic os.link (fails if dest exists), then unlink src
      - Fallback to rename if link isn't possible (e.g., cross-device)
    """
    src = Path(src)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / dest_name

    # ensure we never overwrite
    if dest.exists():
        raise FileExistsError(str(dest))

    try:
        # atomic "claim": fails if dest exists
        os.link(src, dest)
        src.unlink()
        return dest
    except OSError:
        # likely cross-device or filesystem that doesn't
        # support hard links
        # still safe because dest is unique/nonexistent
        src.rename(dest)
        return dest


def _move_to_random_name(src: Path, *, max_tries: int = 50) -> Path:
    dest_dir = src.parent
    suffix = src.suffix

    for _ in range(max_tries):
        nonce = secrets.token_hex(6)  # 12 hex chars
        dest_name = f"{src.stem}-{nonce}{suffix}"
        try:
            return _move_exclusive(src, dest_dir, dest_name)
        except FileExistsError:
            continue

    # extremely unlikely
    nonce = secrets.token_hex(16)
    return _move_exclusive(src, dest_dir, f"{src.stem}-{nonce}{suffix}")
