# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Task routes."""

import asyncio
import logging
import os
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from fastapi_pagination import Page
from sqlalchemy.ext.asyncio import AsyncSession

from waldiez_runner.dependencies import (
    ALLOWED_EXTENSIONS,
    TASK_API_AUDIENCE,
    AsyncRedis,
    Storage,
    get_client_id,
    get_db,
    get_redis,
    get_redis_url,
    get_storage,
)
from waldiez_runner.models import TaskResponse, TaskStatus
from waldiez_runner.services.task_service import TaskService
from waldiez_runner.tasks import broker
from waldiez_runner.tasks import cancel_task as cancel_task_job
from waldiez_runner.tasks import delete_task as delete_task_job
from waldiez_runner.tasks import run_task as run_task_job

from ._common import get_pagination_params

REQUIRED_AUDIENCES = [TASK_API_AUDIENCE]
MAX_TASKS_PER_CLIENT = 3
MAX_TASKS_ERROR = (
    f"Cannot create more than {MAX_TASKS_PER_CLIENT} tasks "
    "at the same time. Please wait for some tasks to finish"
)
LOG = logging.getLogger(__name__)

validate_tasks_audience = get_client_id(*REQUIRED_AUDIENCES)
task_router = APIRouter()


@task_router.get("/tasks/", include_in_schema=False)
@task_router.get(
    "/tasks",
    response_model=Page[TaskResponse],
    summary="Get all client's tasks",
    description="Get all client's tasks.",
)
async def get_client_tasks(
    client_id: Annotated[str, Depends(validate_tasks_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Page[TaskResponse]:
    """Get all tasks.

    Parameters
    ----------
    client_id : str
        The client ID.
    session : AsyncSession
        The database session.

    Returns
    -------
    Page[TaskResponse]
        The tasks.
    """
    params = get_pagination_params()
    return await TaskService.get_client_tasks(session, client_id, params=params)


@task_router.post("/tasks/", include_in_schema=False)
@task_router.post(
    "/tasks",
    response_model=TaskResponse,
    summary="Create a task",
    description="Create a task.",
)
async def create_task(
    client_id: Annotated[str, Depends(validate_tasks_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[Storage, Depends(get_storage)],
    redis_url: Annotated[str, Depends(get_redis_url)],
    file: Annotated[UploadFile, File(...)],
    input_timeout: int = 180,
) -> TaskResponse:
    """Create a task.

    Parameters
    ----------
    client_id : str
        The client ID.
    session : AsyncSession
        The database session dependency.
    storage : Storage
        The storage service dependency.
    redis_url : str
        The Redis URL dependency.
    file : UploadFile
        The file to process.
    input_timeout : int, optional
        The timeout for input requests, by default 180

    Returns
    -------
    TaskResponse
        The created task.

    Raises
    ------
    HTTPException
        If the task cannot be created.
    """
    active_tasks = await TaskService.get_active_client_tasks(
        session,
        client_id=client_id,
    )
    if len(active_tasks.items) >= MAX_TASKS_PER_CLIENT:
        raise HTTPException(status_code=400, detail=MAX_TASKS_ERROR)
    filename = validate_file(file)
    file_hash, saved_path = await storage.save_file(client_id, file)
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
    try:
        task = await TaskService.create_task(
            session,
            client_id=client_id,
            flow_id=file_hash,
            filename=filename,
            input_timeout=input_timeout,
        )
        # relative to root if local, or "bucket" if other (e.g. S3, GCS)
        dst = os.path.join(client_id, str(task.id), filename)
        await storage.move_file(saved_path, dst)
    except BaseException as error:  # pragma: no cover
        await storage.delete_file(saved_path)
        await TaskService.delete_client_flow_task(
            session,
            client_id=client_id,
            flow_id=file_hash,
        )
        if isinstance(error, HTTPException):
            raise HTTPException(
                status_code=error.status_code, detail=error.detail
            ) from error
        LOG.error("Error creating task: %s", error)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from error
    task_response = TaskResponse.model_validate(task, from_attributes=True)
    await _trigger_run_task(task_response, session, storage, redis_url)
    return task_response


@task_router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Get a task by ID",
    description="Get a task by ID for the current client",
)
async def get_task(
    task_id: str,
    client_id: Annotated[str, Depends(validate_tasks_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    """Get a task by ID.

    Parameters
    ----------
    task_id : str
        The task ID.
    client_id : str
        The client ID.
    session : AsyncSession
        The database session.

    Returns
    -------
    Task
        The task.

    Raises
    ------
    HTTPException
        If the task is not found.
    """
    task = await TaskService.get_task(session, task_id=task_id)
    if task is None or task.client_id != client_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@task_router.get(
    "/tasks/{task_id}/download",
    response_model=None,
    summary="Download a task archive",
    description="Download a task archive by ID for the current client",
)
async def download_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    client_id: Annotated[str, Depends(validate_tasks_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> FileResponse | StreamingResponse:
    """Download a task.

    Parameters
    ----------
    task_id : str
        The task ID.
    background_tasks : BackgroundTasks
        Background tasks.
    client_id : str
        The client ID.
    session : AsyncSession
        The database session.
    storage : Storage
        The storage service.

    Returns
    -------
    FileResponse | StreamingResponse
        The response.

    Raises
    ------
    HTTPException
        If the task is not found or an error occurs.
    """
    task = await TaskService.get_task(
        session,
        task_id=task_id,
    )
    if task is None or task.client_id != client_id:
        raise HTTPException(status_code=404, detail="Task not found")
    response = await storage.download_archive(
        client_id, str(task.id), background_tasks
    )
    return response


@task_router.post(
    "/tasks/{task_id}/cancel",
    response_model=TaskResponse,
    summary="Cancel a task",
    description="Cancel a task by ID for the current client",
)
async def cancel_task(
    task_id: str,
    client_id: Annotated[str, Depends(validate_tasks_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[AsyncRedis, Depends(get_redis)],
) -> TaskResponse:
    """Cancel a task.

    Parameters
    ----------
    task_id : str
        The task ID.
    client_id : str
        The client ID that triggered the task.
    session : AsyncSession
        The database session dependency.
    redis : AsyncRedis
        The Redis client dependency.

    Returns
    -------
    Task
        The updated task.

    Raises
    ------
    HTTPException
        If the task is not found or an error occurs.
    """
    task = await TaskService.get_task(
        session,
        task_id=task_id,
    )
    if task is None or task.client_id != client_id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.is_inactive():
        raise HTTPException(
            status_code=400,
            detail=(f"Cannot cancel task with status {task.get_status()}"),
        )
    task.status = TaskStatus.CANCELLED
    await TaskService.update_task_status(
        session,
        task_id=task_id,
        status=TaskStatus.CANCELLED,
        results={"error": "Task cancelled"},
    )
    await _trigger_cancel_task(
        task_id=task_id,
        client_id=client_id,
        session=session,
        redis=redis,
    )
    return TaskResponse.model_validate(task, from_attributes=True)


@task_router.delete(
    "/tasks/{task_id}",
    response_model=None,
    summary="Delete a task",
    description="Delete a task by ID for the current client",
)
async def delete_task(
    task_id: str,
    client_id: Annotated[str, Depends(validate_tasks_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[Storage, Depends(get_storage)],
    force: Annotated[bool | None, False] = False,
) -> Response:
    """Delete a task.

    Parameters
    ----------
    task_id : str
        The task ID.
    client_id : str
        The client ID that triggered the task.
    session : AsyncSession
        The database session.
    storage : Storage
        The storage service.
    force : bool, optional
        Whether to force delete the task, by default False

    Returns
    -------
    Response
        The response (status code 204).

    Raises
    ------
    HTTPException
        If the task is not found or an error occurs.
    """
    task = await TaskService.get_task(
        session,
        task_id=task_id,
    )
    if task is None or task.client_id != client_id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.is_active() and force is not True:
        raise HTTPException(
            status_code=400,
            detail=(f"Cannot delete task with status {task.get_status()}"),
        )
    task.mark_deleted()
    await session.commit()
    await session.refresh(task)
    await _trigger_delete_task(
        task_id=task_id,
        client_id=client_id,
        session=session,
        storage=storage,
    )
    return Response(status_code=204)


@task_router.delete(
    "/tasks",
    response_model=None,
    summary="Delete all tasks",
    description="Delete all tasks for the current client",
)
async def delete_all_tasks(
    client_id: Annotated[str, Depends(validate_tasks_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
    force: Annotated[bool | None, False] = False,
) -> Response:
    """Delete all tasks for a client.

    Parameters
    ----------
    client_id : str
        The client ID.
    session : AsyncSession
        The database session dependency.
    force : bool, optional
        Whether to force delete all tasks, by default False.

    Returns
    -------
    Response
        The response (status code 204).

    Raises
    ------
    HTTPException
        If an error occurs.
    """
    task_ids_to_delete = await TaskService.soft_delete_client_tasks(
        session,
        client_id=client_id,
        inactive_only=force is not True,
    )

    # Soft delete in DB
    if task_ids_to_delete:
        await session.commit()
    return Response(status_code=204)


def validate_file(file: UploadFile) -> str:
    """Validate an uploaded file.

    Parameters
    ----------
    file : UploadFile
        The file to validate.

    Returns
    -------
    str
        The filename.

    Raises
    ------
    HTTPException
        If the file is invalid.
    """
    if not file.filename:  # pragma: no cover
        raise HTTPException(status_code=400, detail="Invalid file")
    if not file.filename.endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Invalid file type")
    return file.filename


async def _trigger_run_task(
    task: TaskResponse,
    session: AsyncSession,
    storage: Storage,
    redis_url: str,
) -> None:
    """Trigger a task."""
    if getattr(broker, "_is_smoke_testing", False) is True:  # pragma: no cover
        LOG.warning("Using fake Redis, running task in background")
        bg_task = asyncio.create_task(
            run_task_job(
                task=task,
                db_session=session,
                storage=storage,
                redis_url=redis_url,
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
        await run_task_job.kiq(task=task)


async def _trigger_cancel_task(
    task_id: str,
    client_id: str,
    session: AsyncSession,
    redis: AsyncRedis,
) -> None:
    """Trigger a task cancellation."""
    if getattr(broker, "_is_smoke_testing", False) is True:  # pragma: no cover
        LOG.warning("Using fake Redis, cancelling task in background")
        bg_task = asyncio.create_task(
            cancel_task_job(
                task_id=task_id,
                client_id=client_id,
                db_session=session,
                redis=redis,
            )
        )
        bg_task.add_done_callback(
            lambda t: (
                LOG.exception("cancel_task_job failed", exc_info=t.exception())
                if t.exception()
                else LOG.info("cancel_task_job succeeded")
            )
        )
    else:
        await cancel_task_job.kiq(
            task_id=task_id,
            client_id=client_id,
        )


async def _trigger_delete_task(
    task_id: str,
    client_id: str,
    session: AsyncSession,
    storage: Storage,
) -> None:
    """Trigger a task deletion."""
    if getattr(broker, "_is_smoke_testing", False) is True:
        LOG.warning("Using fake Redis, deleting task in background")
        bg_task = asyncio.create_task(
            delete_task_job(
                task_id=task_id,
                client_id=client_id,
                db_session=session,
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
