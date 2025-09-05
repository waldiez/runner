# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pyright: reportPossiblyUnboundVariable=false

"""Task routes."""

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Annotated, Any, Optional, cast

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from fastapi_pagination import Page
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from typing_extensions import Literal

from waldiez_runner.config.settings import Settings
from waldiez_runner.dependencies import (
    ALLOWED_EXTENSIONS,
    TASK_API_AUDIENCE,
    Storage,
    app_state,
    get_client_id,
    get_db,
    get_filename_from_url,
    get_storage,
)
from waldiez_runner.dependencies.context import (
    RequestContext,
    get_request_context,
)
from waldiez_runner.middleware.slow_api import limiter
from waldiez_runner.models import TaskStatus
from waldiez_runner.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from waldiez_runner.services.task_service import TaskService
from waldiez_runner.tasks import broker
from waldiez_runner.tasks import delete_task as delete_task_job
from waldiez_runner.tasks import run_task as run_task_job

from ._common import Order, get_pagination_params
from ._env_vars import get_env_vars

REQUIRED_AUDIENCES = [TASK_API_AUDIENCE]
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
LOG = logging.getLogger(__name__)
TaskSort = Literal[
    "id",
    "flow_id",
    "filename",
    "status",
]
validate_tasks_audience = get_client_id(*REQUIRED_AUDIENCES)
task_router = APIRouter()


class InputResponse(BaseModel):
    """Input response model."""

    request_id: str
    data: str


async def _check_user_can_run_task(context: RequestContext) -> None:
    """Check if the user is allowed to run a task.

    Parameters
    ----------
    context : RequestContext
        The request context containing external user info.

    Raises
    ------
    HTTPException
        If the user is not allowed to run the task or if the check fails.
    """

    _validate_settings()
    settings = cast(Settings, app_state.settings)

    if not settings.enable_external_auth:
        return

    if not _is_permission_check_configured(settings):
        return

    user_id = _extract_user_id(context)
    await _verify_user_permission(settings, user_id)


def _validate_settings() -> None:
    """Validate that application settings are initialized."""
    if not app_state.settings:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Settings not initialized",
        )


def _is_permission_check_configured(settings: Settings) -> bool:
    """Check if permission verification is properly configured."""
    verify_url = settings.task_permission_verify_url
    secret = settings.task_permission_secret

    if not verify_url or not secret:
        LOG.warning("External auth verify URL or secret not configured")
        return False
    return True


def _extract_user_id(context: RequestContext) -> str:
    """Extract user ID from the request context."""
    if not context.external_user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User information not available for permission check",
        )

    user_id = context.external_user_info.get(
        "sub"
    ) or context.external_user_info.get("id")

    if not user_id or not isinstance(user_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user identifier for permission check",
        )

    return user_id


async def _verify_user_permission(settings: Settings, user_id: str) -> None:
    """Verify user permission by making an HTTP request."""
    try:
        data = await _make_permission_request(settings, user_id)
        # Assuming server returns 200 only if can_run is true
        # If can_run is false, server returns 429
    except HTTPException:
        # Re-raise HTTPException instances (like 429 errors)
        # without wrapping them
        raise
    except httpx.HTTPStatusError as error:
        if error.response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            try:
                data = error.response.json()
                reason = data.get("reason", "Too many requests")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=reason,
                ) from error
            except (ValueError, KeyError):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests",
                ) from error
        LOG.error(
            "Permission check failed with status %s", error.response.status_code
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify user permission",
        ) from error
    except ValueError as error:
        LOG.error("Invalid JSON response from permission check: %s", error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid response from permission check",
        ) from error
    except Exception as error:
        LOG.error("Unexpected error during permission check: %s", error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify user permission",
        ) from error


async def _make_permission_request(
    settings: Settings, user_id: str
) -> dict[str, Any]:
    """Make the HTTP request to verify user permission."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            settings.task_permission_verify_url,
            params={"user_id": user_id},
            headers={"X-Runner-Secret-Key": settings.task_permission_secret},
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()


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
    search: Annotated[str | None, Query(description="A term to search")] = None,
    order_by: Annotated[
        TaskSort | None,
        Query(description="The field to sort the results"),
    ] = None,
    order_type: Annotated[
        Order | None,
        Query(description="The order direction, can be 'asc' or 'desc'"),
    ] = None,
) -> Page[TaskResponse]:
    """Get all tasks.

    Parameters
    ----------
    client_id : str
        The client ID.
    session : AsyncSession
        The database session.
    search : str | None
        A search term to filter the tasks.
    order_by : str | None
        The field to sort the tasks.
    order_type : str | None
        The order to sort the tasks. Can be "asc" or "desc".

    Returns
    -------
    Page[TaskResponse]
        The tasks.
    """
    params = get_pagination_params()
    return await TaskService.get_client_tasks(
        session,
        client_id,
        params=params,
        search=search,
        order_by=order_by,
        descending=order_type == "desc",
    )


# pylint: disable=too-many-locals,too-many-arguments
# pylint: disable=too-many-positional-arguments
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
    context: Annotated[RequestContext, Depends(get_request_context)],
    # file: Annotated[UploadFile, File(...)],
    file: Optional[UploadFile] = None,
    file_url: Optional[str] = Form(None),
    env_vars: Optional[str] = Form(
        None, description="JSON string of environment variables"
    ),
    input_timeout: int = Form(180),
    schedule_type: Optional[Literal["once", "cron"]] = Form(None),
    scheduled_time: Optional[datetime] = Form(None),
    cron_expression: Optional[str] = Form(None),
    expires_at: Optional[datetime] = Form(None),
    trigger_now: bool = Form(False),
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
    context : RequestContext
        The request context containing external user info.
    file : Optional[UploadFile]
        The file to process.
    file_url : Optional[str], optional
        The URL of the file to process, by default None
    env_vars : Optional[str], optional
        A JSON string of environment variables, by default None
    input_timeout : int, optional
        The timeout for input requests, by default 180
    schedule_type : Optional[Literal["once", "cron"]], optional
        The type of schedule, by default None
    scheduled_time : Optional[datetime], optional
        The time to schedule the task, by default None
    cron_expression : Optional[str], optional
        The cron expression for scheduling, by default None
    expires_at : Optional[datetime], optional
        The expiration time for the task, by default None
    trigger_now : bool, optional
        Whether to also trigger the task now (if cron), by default False

    Returns
    -------
    TaskResponse
        The created task.

    Raises
    ------
    HTTPException
        If the task cannot be created.
    """
    # Check user permission before creating task
    await _check_user_can_run_task(context)

    if not file and not file_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either file or file_url must be provided",
        )
    if file and file_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only one of file or file_url can be provided",
        )
    (
        file_hash,
        filename,
        save_path,
        environment_vars,
    ) = await validate_task_input(
        session=session,
        file=file,
        file_url=file_url,
        env_vars=env_vars,
        client_id=client_id,
        storage=storage,
        schedule_type=schedule_type,
    )
    try:
        task_create = TaskCreate(
            client_id=client_id,
            flow_id=file_hash,
            filename=filename,
            input_timeout=input_timeout,
            schedule_type=schedule_type,
            scheduled_time=scheduled_time,
            cron_expression=cron_expression,
            expires_at=expires_at,
        )
    except ValidationError as error:
        await storage.delete_file(save_path)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error.json(),
        ) from error
    try:
        task = await TaskService.create_task(
            session,
            task_create=task_create,
        )
        # relative to root if local, or "bucket" if other (e.g. S3, GCS)
        dst = os.path.join(client_id, str(task.id), filename)
        await storage.move_file(save_path, dst)
    except BaseException as error:  # pragma: no cover
        await storage.delete_file(save_path)
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
    if task.schedule_type is None or trigger_now:
        await _trigger_run_task(
            task=task_response,
            env_vars=environment_vars,
            session=session,
            storage=storage,
        )
    if task.schedule_type is not None:
        await _schedule_task(
            task=task_response,
            _session=session,
            _storage=storage,
            _env_vars=environment_vars,
        )
    return task_response


@task_router.get("/tasks/{task_id}/", include_in_schema=False)
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return TaskResponse.model_validate(task)


@task_router.patch(
    "/tasks/{task_id}/",
    response_model=TaskResponse,
    include_in_schema=False,
)
@task_router.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Update a task",
    description="Update a task by ID for the current client",
)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    client_id: Annotated[str, Depends(validate_tasks_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    """Update a task.

    Parameters
    ----------
    task_id : str
        The task ID.
    task_update : TaskUpdate
        The task update data.
    client_id : str
        The client ID.
    session : AsyncSession
        The database session.

    Returns
    -------
    TaskResponse
        The updated task.

    Raises
    ------
    HTTPException
        If the task is not found or an error occurs.
    """
    task = await TaskService.get_task(session, task_id=task_id)
    if task is None or task.client_id != client_id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.is_inactive():
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update task with status {task.get_status()}",
        )
    updated = await TaskService.update_task(
        session, task_id=task_id, task_update=task_update
    )
    return TaskResponse.model_validate(updated, from_attributes=True)


@task_router.post("/tasks/{task_id}/input/", include_in_schema=False)
@task_router.post("/tasks/{task_id}/input")
async def on_input_request(
    task_id: str,
    message: InputResponse,
    background_tasks: BackgroundTasks,
    db_session: Annotated[AsyncSession, Depends(get_db)],
    client_id: Annotated[str, Depends(validate_tasks_audience)],
) -> Response:
    """Task input

    Parameters
    ----------
    task_id : str
        The task ID.
    message : InputResponse
        The input response message.
    background_tasks : BackgroundTasks
        The background tasks.
    db_session : AsyncSession
        The database session.
    client_id : str
        The client ID.

    Returns
    -------
    Response
        The response (status code 204).

    Raises
    ------
    HTTPException
        If the message or the task_id is invalid.

    """
    LOG.debug("Received input request: %s", message)
    try:
        task = await TaskService.get_task(db_session, task_id=task_id)
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        ) from e
    if task is None or task.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    if task.status != TaskStatus.WAITING_FOR_INPUT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input request",
        )
    if message.request_id != task.input_request_id:
        LOG.warning(
            "Received invalid input request: %s vs %s",
            message.request_id,
            task.input_request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input request",
        )
    background_tasks.add_task(
        publish_task_input_response,
        task_id=task_id,
        message=message,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@task_router.get(
    "/tasks/{task_id}/download/",
    response_model=None,
    include_in_schema=False,
)
@task_router.get(
    "/tasks/{task_id}/download",
    response_model=None,
    summary="Download a task archive",
    description="Download a task archive by ID for the current client",
)
@limiter.exempt  # type: ignore
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
    "/tasks/{task_id}/cancel/",
    response_model=TaskResponse,
    include_in_schema=False,
)
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
            detail=f"Cannot cancel task with status {task.get_status()}",
        )
    task.status = TaskStatus.CANCELLED
    await TaskService.update_task_status(
        session,
        task_id=task_id,
        status=TaskStatus.CANCELLED,
        results={"detail": "Task cancelled"},
    )
    await publish_task_cancellation(task_id=task_id)
    return TaskResponse.model_validate(task, from_attributes=True)


@task_router.delete(
    "/tasks/{task_id}/",
    response_model=None,
    include_in_schema=False,
)
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
            detail=f"Cannot delete task with status {task.get_status()}",
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
    "/tasks/",
    response_model=None,
    include_in_schema=False,
)
@task_router.delete(
    "/tasks",
    response_model=None,
    summary="Delete multiple tasks",
    description="Delete multiple tasks for the current client",
)
async def delete_tasks(
    client_id: Annotated[str, Depends(validate_tasks_audience)],
    session: Annotated[AsyncSession, Depends(get_db)],
    ids: Annotated[list[str] | None, Query()] = None,
    force: Annotated[bool | None, False] = False,
) -> Response:
    """Delete all tasks for a client.

    Parameters
    ----------
    client_id : str
        The client ID.
    session : AsyncSession
        The database session dependency.
    ids : list[str] | None, optional
        The list of task IDs to delete, by default None
        (delete all tasks if None).
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
        ids=ids,
        inactive_only=force is not True,
    )

    # Soft delete in DB
    if task_ids_to_delete:
        await session.commit()
    return Response(status_code=204)


async def publish_task_input_response(
    task_id: str,
    message: InputResponse,
) -> None:
    """Publish task input response to Redis.

    Parameters
    ----------
    task_id : str
        The task ID.
    message : InputResponse
        The input response message.

    Raises
    ------
    RuntimeError
        If the Redis connection manager is not initialized.
    """
    if not app_state.redis:  # pragma: no cover
        raise RuntimeError("Redis manager not initialized")
    async with app_state.redis.contextual_client(True) as redis:
        try:
            await redis.publish(
                channel=f"task:{task_id}:input_response",
                message=json.dumps(
                    {"request_id": message.request_id, "data": message.data}
                ),
            )
        except BaseException as e:  # pylint: disable=broad-exception-caught
            LOG.warning("Failed to publish task input response message: %s", e)


async def _trigger_run_task(
    task: TaskResponse,
    session: AsyncSession,
    storage: Storage,
    env_vars: dict[str, str],
) -> None:
    """Trigger a task."""
    if not app_state.redis:  # pragma: no cover
        raise RuntimeError("Redis not initialized")
    if getattr(broker, "_is_smoke_testing", False) is True:  # pragma: no cover
        LOG.warning("Using fake Redis, running task in background")
        bg_task = asyncio.create_task(
            run_task_job(
                task=task,
                env_vars=env_vars,
                db_session=session,
                storage=storage,
                redis_manager=app_state.redis,
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
        await run_task_job.kiq(task=task, env_vars=env_vars)


async def publish_task_cancellation(
    task_id: str,
) -> None:
    """Publish task cancellation message to Redis.

    Parameters
    ----------
    task_id : str
        The task ID.

    Raises
    ------
    HTTPException
        If the Redis publish fails or if the Redis manager is not initialized.
    """
    if not app_state.redis:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail="Redis manager not initialized",
        )
    async with app_state.redis.contextual_client(True) as redis:
        try:
            await redis.publish(
                channel=f"task:{task_id}:status",
                message=json.dumps(
                    {
                        "task_id": task_id,
                        "status": TaskStatus.CANCELLED.value,
                        "data": {"detail": "Task Cancelled"},
                    }
                ),
            )
        except BaseException as e:
            LOG.warning("Failed to publish task cancellation message: %s", e)
            raise HTTPException(
                status_code=500,
                detail="Failed to publish task cancellation message",
            ) from e


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


def _validate_uploaded_file(file: UploadFile) -> str:
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


async def _schedule_task(
    task: TaskResponse,
    _session: AsyncSession,
    _storage: Storage,
    _env_vars: dict[str, str],  # pylint: disable=unused-argument
) -> None:
    """Schedule a task.

    Parameters
    ----------
    task : TaskResponse
        The task to schedule.
    session : AsyncSession
        The database session.
    storage : Storage
        The storage service.
    env_vars : dict[str, str]
        The environment variables for the task.
    """
    LOG.debug(
        "Scheduling task %s with schedule type %s",
        task.id,
        task.schedule_type,
    )
    raise NotImplementedError(
        "Scheduling tasks is not implemented yet. "
        "Please check the documentation for updates."
    )
