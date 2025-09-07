# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pyright: reportPossiblyUnboundVariable=false

"""Task routes."""

import hashlib
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Literal

from waldiez_runner.dependencies import (
    ALLOWED_EXTENSIONS,
    Storage,
    get_filename_from_url,
)
from waldiez_runner.services.task_service import TaskService

from .env_vars import get_env_vars

MAX_TASKS_PER_CLIENT = 3
MAX_TASKS_ERROR = (
    f"Cannot create more than {MAX_TASKS_PER_CLIENT} tasks "
    "at the same time. Please wait for some tasks to finish"
)
ALLOWED_REMOTE_URL_SCHEMES = (
    # "http",
    "https",
    # "ftp",
    "ftps",
    "sftp",
    "s3",
    # "gs",
)


def _validate_uploaded_file(file: UploadFile) -> str:
    """Validate an uploaded file."""
    if not file.filename:  # pragma: no cover
        raise HTTPException(status_code=400, detail="Invalid file")
    if not file.filename.endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Invalid file type")
    return file.filename


async def validate_task_input(
    session: AsyncSession,
    file: Optional[UploadFile],
    file_url: Optional[str],
    env_vars: Optional[str],
    client_id: str,
    storage: Storage,
    schedule_type: Optional[Literal["once", "cron"]] = None,
) -> tuple[str, str, str, dict[str, str]]:
    """Validate the uploaded file.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    file : Optional[UploadFile]
        The file to validate.
    file_url : Optional[str]
        The URL of the file to validate, by default None
    env_vars : Optional[str]
        A JSON string of environment variables, by default None
    client_id : str
        The client ID.
    storage : Storage
        The storage service.
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
    active_tasks = await TaskService.get_active_client_tasks(
        session,
        client_id=client_id,
    )
    if len(active_tasks.items) >= MAX_TASKS_PER_CLIENT:
        raise HTTPException(status_code=400, detail=MAX_TASKS_ERROR)
    saved_path: str = ""
    file_hash: str = ""
    filename: str = ""
    if file:
        filename = _validate_uploaded_file(file)
        file_hash, saved_path = await storage.save_file(client_id, file)
    if file_url:
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
    if not file_hash or not filename or not saved_path:
        raise HTTPException(
            status_code=400,
            detail="Invalid file or file URL",
        )
    filename_hash = hashlib.md5(
        filename.encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:8]
    file_hash = f"{file_hash}-{filename_hash}"
    active_task = next(
        (task for task in active_tasks.items if task.flow_id == file_hash), None
    )
    if active_task:
        await storage.delete_file(saved_path)
        raise HTTPException(
            status_code=400,
            detail=(
                f"A task with the same file already exists. "
                f"Task ID: {active_task.id}, "
                f"status: {active_task.get_status()}"
            ),
        )
    environment_vars = get_env_vars(env_vars)
    return file_hash, filename, saved_path, environment_vars
