# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pyright: reportPossiblyUnboundVariable=false
# pyright: reportCallInDefaultInitializer=false

"""Task routes."""

import logging
import os
from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from fastapi_pagination import Page
from pydantic import ValidationError
from starlette import status
from typing_extensions import Literal

from waldiez_runner.config import Settings
from waldiez_runner.dependencies import (
    ADMIN_API_AUDIENCE,
    TASK_API_AUDIENCE,
    DatabaseManager,
    Storage,
    get_admin_client_id,
    get_client_id,
    get_client_id_with_admin_check,
    get_db_manager,
    get_settings,
    get_storage,
)
from waldiez_runner.dependencies.context import (
    RequestContext,
    get_request_context,
)
from waldiez_runner.models import TaskStatus
from waldiez_runner.schemas.task import (
    InputResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from waldiez_runner.services.task_service import TaskService

from .pagination import Order, get_pagination_params
from .task_input_validation import (
    validate_task_input,
    validate_uploaded_file,
    validate_waldiez_flow,
)
from .task_jobs import schedule_task, trigger_delete_task, trigger_run_task
from .task_permission import check_user_can_run_task
from .task_pub import publish_task_cancellation, publish_task_input_response

REQUIRED_AUDIENCES = [TASK_API_AUDIENCE]
ADMIN_AUDIENCES = [ADMIN_API_AUDIENCE]

LOG = logging.getLogger(__name__)
TaskSort = Literal[
    "id",
    "flow_id",
    "filename",
    "status",
]
validate_tasks_audience = get_client_id(*REQUIRED_AUDIENCES)
validate_admin_audience = get_admin_client_id(*ADMIN_AUDIENCES)
validate_client_with_admin = get_client_id_with_admin_check()
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
    db: Annotated[DatabaseManager, Depends(get_db_manager)],
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
    db : DatabaseManager
        The database session manager.
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
    async with db.session() as session:
        return await TaskService.get_client_tasks(
            session,
            client_id,
            params=params,
            search=search,
            order_by=order_by,
            descending=order_type == "desc",
        )


@task_router.get(
    "/admin/tasks",
    response_model=Page[TaskResponse],
    summary="Get all tasks (admin only)",
    description="Get all tasks from all users. Requires admin audience.",
)
async def get_all_tasks(
    _: Annotated[str, Depends(validate_admin_audience)],
    db: Annotated[DatabaseManager, Depends(get_db_manager)],
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
    """Get all tasks from all users.

    Parameters
    ----------
    db : DatabaseManager
        The database session manager.
    search : str | None
        A search term to filter the tasks.
    order_by : str | None
        The field to sort the tasks.
    order_type : str | None
        The order to sort the tasks. Can be "asc" or "desc".

    Returns
    -------
    Page[TaskResponse]
        All tasks from all users.
    """
    params = get_pagination_params()
    async with db.session() as session:
        return await TaskService.get_all_tasks(
            session,
            params=params,
            search=search,
            order_by=order_by,
            descending=order_type == "desc",
        )


# pylint: disable=too-many-locals,too-many-arguments
# pylint: disable=too-many-positional-arguments,too-many-try-statements
@task_router.post("/tasks/", include_in_schema=False)
@task_router.post(
    "/tasks",
    response_model=TaskResponse,
    summary="Create a task",
    description="Create a task.",
)
async def create_task(
    client_id: Annotated[str, Depends(validate_tasks_audience)],
    db_manager: Annotated[DatabaseManager, Depends(get_db_manager)],
    storage: Annotated[Storage, Depends(get_storage)],
    context: Annotated[RequestContext, Depends(get_request_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile | None = None,
    file_url: str | None = Form(None),
    filename: str | None = Form(None),
    env_vars: str | None = Form(
        None, description="JSON string of environment variables"
    ),
    input_timeout: int = Form(180),
    schedule_type: Literal["once", "cron"] | None = Form(None),
    scheduled_time: datetime | None = Form(None),
    cron_expression: str | None = Form(None),
    expires_at: datetime | None = Form(None),
    trigger_now: bool = Form(False),
) -> TaskResponse:
    """Create a task.

    Parameters
    ----------
    client_id : str
        The client ID.
    db_manager : DatabaseManager
        The database session manager dependency.
    storage : Storage
        The storage service dependency.
    context : RequestContext
        The request context containing external user info.
    settings : Settings
        The settings to get the max_jobs config.
    file : Optional[UploadFile]
        The file to process.
    file_url : str | None, optional
        The URL of the file to process, by default None
    filename : str | None, optional
        The local file of a previously uploaded file to use.
    env_vars : str | None, optional
        A JSON string of environment variables, by default None
    input_timeout : int, optional
        The timeout for input requests, by default 180
    schedule_type : Optional[Literal["once", "cron"]], optional
        The type of schedule, by default None
    scheduled_time : Optional[datetime], optional
        The time to schedule the task, by default None
    cron_expression : str | None, optional
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
    await check_user_can_run_task(context)

    if not file and not file_url and not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either file, file_url or filename must be provided",
        )
    provided = sum(bool(item) for item in [file, file_url, filename])
    if provided > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only one of `file`, `file_url` or `filename` can be provided"
            ),
        )
    (
        file_hash,
        file_name,
        save_path,
        environment_vars,
    ) = await validate_task_input(
        db=db_manager,
        file=file,
        file_url=file_url,
        file_path=filename,
        env_vars=env_vars,
        client_id=client_id,
        storage=storage,
        max_jobs=settings.max_jobs,
        schedule_type=schedule_type,
    )
    try:
        task_create = TaskCreate(
            client_id=client_id,
            flow_id=file_hash,
            filename=file_name,
            input_timeout=input_timeout,
            schedule_type=schedule_type,
            scheduled_time=scheduled_time,
            cron_expression=cron_expression,
            expires_at=expires_at,
        )
    except ValidationError as error:
        await storage.delete_file(save_path)
        raise HTTPException(
            status_code=422,
            detail=error.json(),
        ) from error
    try:
        async with db_manager.session() as session:
            task = await TaskService.create_task(
                session,
                task_create=task_create,
            )
        # relative to root if local, or "bucket" if other (e.g. S3, GCS)
        dst = os.path.join(client_id, str(task.id), file_name)
        await storage.move_file(save_path, dst)
    except BaseException as error:  # pragma: no cover
        await storage.delete_file(save_path)
        async with db_manager.session() as session:
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
        await trigger_run_task(
            task=task_response,
            env_vars=environment_vars,
            db_manager=db_manager,
            storage=storage,
        )
    if task.schedule_type is not None:
        await schedule_task(
            task=task_response,
            db_manager=db_manager,
            storage=storage,
            env_vars=environment_vars,
        )
    return task_response


@task_router.post("/tasks/upload/", include_in_schema=False)
@task_router.post(
    "/tasks/upload",
    summary="Upload a workflow to be later used in a new task.",
    description="Upload a workflow to be later used in a new task.",
)
async def upload_task_workflow(
    client_id: Annotated[str, Depends(validate_tasks_audience)],
    storage: Annotated[Storage, Depends(get_storage)],
    file: Annotated[UploadFile, File(...)],
) -> Response:
    """Upload a workflow file to be later used in a new task.

    Parameters
    ----------
    client_id : str
        The client ID.
    storage : Storage
        The storage service dependency.
    file : UploadFile
        The uploaded file.

    Returns
    -------
    Response
        No content (204) if successfully saved.

    Raises
    ------
    HTTPException
        If the request is invalid.
    """
    filename, _, save_path = await validate_uploaded_file(
        file, client_id=client_id, storage=storage
    )
    try:
        await validate_waldiez_flow(save_path)
    except HTTPException:
        await storage.delete_file(save_path)
        raise
    try:
        dst = os.path.join(client_id, filename)
        await storage.move_file(save_path, dst)
    except HTTPException:
        await storage.delete_file(save_path)
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@task_router.get("/tasks/{task_id}/", include_in_schema=False)
@task_router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Get a task by ID",
    description=(
        "Get a task by ID. Admins can view any task, regular users can "
        "only view their own."
    ),
)
async def get_task(
    task_id: str,
    client_id_and_admin: Annotated[
        tuple[str, bool], Depends(validate_client_with_admin)
    ],
    db: Annotated[DatabaseManager, Depends(get_db_manager)],
) -> TaskResponse:
    """Get a task by ID.

    Parameters
    ----------
    task_id : str
        The task ID.
    client_id_and_admin : tuple[str, bool]
        The client ID and admin status.
    db : DatabaseManager
        The database session manager.

    Returns
    -------
    Task
        The task.

    Raises
    ------
    HTTPException
        If the task is not found.
    """
    client_id, is_admin = client_id_and_admin
    async with db.session() as session:
        task = await TaskService.get_task(session, task_id=task_id)
    if task is None or (not is_admin and task.client_id != client_id):
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
    description=(
        "Update a task by ID. Admins can update any task, regular users"
        " can only update their own."
    ),
)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    client_id_and_admin: Annotated[
        tuple[str, bool], Depends(validate_client_with_admin)
    ],
    db: Annotated[DatabaseManager, Depends(get_db_manager)],
) -> TaskResponse:
    """Update a task.

    Parameters
    ----------
    task_id : str
        The task ID.
    task_update : TaskUpdate
        The task update data.
    client_id_and_admin : tuple[str, bool]
        The client ID and admin status.
    db : DatabaseManager
        The database session manager.

    Returns
    -------
    TaskResponse
        The updated task.

    Raises
    ------
    HTTPException
        If the task is not found or an error occurs.
    """
    client_id, is_admin = client_id_and_admin
    async with db.session() as session:
        task = await TaskService.get_task(session, task_id=task_id)
    if task is None or (not is_admin and task.client_id != client_id):
        raise HTTPException(status_code=404, detail="Task not found")
    if task.is_inactive():
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update task with status {task.get_status()}",
        )
    async with db.session() as session:
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
    db: Annotated[DatabaseManager, Depends(get_db_manager)],
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
    db : DatabaseManager
        The database session manager.
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
        async with db.session() as session:
            task = await TaskService.get_task(session, task_id=task_id)
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
    description=(
        "Download a task archive by ID. Admins can download any task, "
        "regular users can only download their own."
    ),
)
async def download_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    client_id_and_admin: Annotated[
        tuple[str, bool], Depends(validate_client_with_admin)
    ],
    db: Annotated[DatabaseManager, Depends(get_db_manager)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> FileResponse | StreamingResponse:
    """Download a task.

    Parameters
    ----------
    task_id : str
        The task ID.
    background_tasks : BackgroundTasks
        Background tasks.
    client_id_and_admin : tuple[str, bool]
        The client ID and admin status.
    db : DatabaseManager
        The database session manager.
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
    client_id, is_admin = client_id_and_admin
    async with db.session() as session:
        task = await TaskService.get_task(
            session,
            task_id=task_id,
        )
    if task is None or (not is_admin and task.client_id != client_id):
        raise HTTPException(status_code=404, detail="Task not found")
    task_dir = os.path.join(task.client_id, str(task.id))
    if not await storage.is_dir(task_dir):
        raise HTTPException(
            status_code=404, detail="Task archive does not exist"
        )
    response = await storage.download_archive(
        task.client_id, str(task.id), background_tasks
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
    description=(
        "Cancel a task by ID. Admins can cancel any task, "
        "regular users can only cancel their own."
    ),
)
async def cancel_task(
    task_id: str,
    client_info: Annotated[
        tuple[str, bool], Depends(validate_client_with_admin)
    ],
    db: Annotated[DatabaseManager, Depends(get_db_manager)],
) -> TaskResponse:
    """Cancel a task.

    Parameters
    ----------
    task_id : str
        The task ID.
    client_info : tuple[str, bool]
        The client ID and whether the user is admin.
    db : DatabaseManager
        The database session manager.

    Returns
    -------
    Task
        The updated task.

    Raises
    ------
    HTTPException
        If the task is not found or an error occurs.
    """
    client_id, is_admin = client_info

    async with db.session() as session:
        task = await TaskService.get_task(
            session,
            task_id=task_id,
        )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # If not admin, check if task belongs to the user
    if not is_admin and task.client_id != client_id:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.is_inactive():
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel task with status {task.get_status()}",
        )
    task.status = TaskStatus.CANCELLED
    async with db.session() as session:
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
    description=(
        "Delete a task by ID. Admins can delete any task, "
        "regular users can only delete their own."
    ),
)
async def delete_task(
    task_id: str,
    client_info: Annotated[
        tuple[str, bool], Depends(validate_client_with_admin)
    ],
    db: Annotated[DatabaseManager, Depends(get_db_manager)],
    storage: Annotated[Storage, Depends(get_storage)],
    force: Annotated[bool | None, False] = False,
) -> Response:
    """Delete a task.

    Parameters
    ----------
    task_id : str
        The task ID.
    client_info : tuple[str, bool]
        The client ID and whether the user is admin.
    db : DatabaseManager
        The database session manager.
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
    client_id, is_admin = client_info

    async with db.session() as session:
        task = await TaskService.get_task(
            session,
            task_id=task_id,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        # If not admin, check if task belongs to the user
        if not is_admin and task.client_id != client_id:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.is_active() and force is not True:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete task with status {task.get_status()}",
            )
        task.mark_deleted()
        await session.commit()
        await session.refresh(task)
    await trigger_delete_task(
        task_id=task_id,
        client_id=client_id,
        db_manager=db,
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
    description=(
        "Delete multiple tasks. Admins can delete any tasks by ID, "
        "regular users can only delete their own."
    ),
)
async def delete_tasks(
    client_id_and_admin: Annotated[
        tuple[str, bool], Depends(validate_client_with_admin)
    ],
    db: Annotated[DatabaseManager, Depends(get_db_manager)],
    ids: Annotated[list[str] | None, Query()] = None,
    force: Annotated[bool | None, False] = False,
) -> Response:
    """Delete all tasks for a client.

    Parameters
    ----------
    client_id_and_admin : tuple[str, bool]
        The client ID and admin status.
    db : DatabaseManager
        The database session manager.
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
    client_id, is_admin = client_id_and_admin

    if not ids:
        # Require specific task IDs to prevent accidental deletion of all tasks
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task IDs must be specified for deletion",
        )

    async with db.session() as session:
        # Delete specific tasks by ID
        if is_admin:
            # Admins can delete any tasks by ID
            task_ids_to_delete = await TaskService.soft_delete_tasks_by_ids(
                session,
                task_ids=ids,
                inactive_only=force is not True,
            )
        else:
            # Regular users can only delete their own tasks by ID
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
