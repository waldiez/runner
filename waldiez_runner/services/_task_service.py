# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=line-too-long
"""Task management service."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Sequence

import sqlalchemy.sql.functions
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import asc, desc, or_
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql.expression import delete, update

from waldiez_runner.models.task import Task
from waldiez_runner.models.task_status import TaskStatus
from waldiez_runner.schemas.task import TaskCreate, TaskResponse, TaskUpdate


def task_transformer(items: Sequence[Task]) -> Sequence[TaskResponse]:
    """Transform tasks to responses.

    Parameters
    ----------
    items : Sequence[Task]
        List of tasks.

    Returns
    -------
    Sequence[TaskResponse]
        List of task responses.
    """
    # return [TaskResponse.from_orm(task) for task in items]
    return [TaskResponse.model_validate(task) for task in items]


async def get_client_tasks(
    session: AsyncSession,
    client_id: str,
    params: Params,
    search: str | None = None,
    order_by: str | None = None,
    descending: bool = False,
) -> Page[TaskResponse]:
    """Retrieve all tasks for a client.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    client_id : str
        Client ID.
    params : Params
        Pagination parameters.
    search : str | None
        Optional search term.
    order_by : str | None
        Optional field to order by.
    descending : bool
        Whether to order in descending order. Default is False.

    Returns
    -------
    Sequence[TaskResponse]
        List of tasks for the client.

    Raises
    ------
    ValueError
        If an invalid field is provided for ordering.
    """

    query = select(Task).where(
        Task.client_id == client_id, Task.deleted_at.is_(None)
    )
    if search:
        # a simple ilike
        query = query.where(
            or_(
                Task.filename.ilike(f"%{search}%"),
                Task.status.ilike(f"%{search}%"),
            )
        )
    if order_by:
        if order_by not in Task.__table__.columns:  # pragma: no cover
            # already checked in the router
            raise ValueError(f"Invalid field for ordering: {order_by}")
        if descending:
            query = query.order_by(desc(getattr(Task, order_by)))
        else:
            query = query.order_by(asc(getattr(Task, order_by)))
    else:
        query = query.order_by(
            desc(Task.created_at) if descending else asc(Task.created_at)
        )

    page = await apaginate(
        session,
        query,
        params=params,
        transformer=task_transformer,
    )
    return page


async def create_task(
    session: AsyncSession,
    task_create: TaskCreate,
) -> Task:
    """Create a new task in the database.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    task_create : TaskCreate
        Task creation data.

    Returns
    -------
    Task
        The created task.
    """
    task = Task(
        client_id=task_create.client_id,
        flow_id=task_create.flow_id,
        filename=task_create.filename,
        input_timeout=task_create.input_timeout,
        schedule_type=task_create.schedule_type,
        scheduled_time=task_create.scheduled_time,
        cron_expression=task_create.cron_expression,
        expires_at=task_create.expires_at,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def update_task(
    session: AsyncSession,
    task_id: str,
    task_update: TaskUpdate,
) -> Task | None:
    """Update a task in the database.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    task_id : str
        Task ID.
    task_update : TaskUpdate
        Task update data.

    Returns
    -------
    Task | None
        The updated task or None if not found.
    """
    query = (
        update(Task)
        .where(Task.id == task_id, Task.deleted_at.is_(None))
        .values(**task_update.model_dump(exclude_unset=True))
        .returning(Task)
    )
    result = await session.execute(query)
    await session.commit()
    return result.scalar_one_or_none()


async def get_task(
    session: AsyncSession,
    task_id: str,
) -> Task | None:
    """Retrieve a task by ID and optionally by client.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    task_id : str
        Task ID.

    Returns
    -------
    Task | None
        Task instance or None if not found.
    """
    query = select(Task).where(Task.id == task_id, Task.deleted_at.is_(None))
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_active_client_tasks(
    async_session: AsyncSession,
    client_id: str,
) -> Page[Task]:
    """Get all active tasks for a client.

    Parameters
    ----------
    async_session : AsyncSession
        SQLAlchemy async session.
    client_id : str
        Client ID.

    Returns
    -------
    Page[Task]
        List of active tasks for the client.
    """
    page = await apaginate(
        async_session,
        select(Task)
        .where(
            Task.client_id == client_id,
            Task.status.notin_(
                [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED]
            ),
            Task.deleted_at.is_(None),
        )
        .order_by(Task.updated_at.desc()),
        params=Params(page=1, size=100),
    )
    return page


async def get_tasks_to_delete(
    session: AsyncSession,
    older_than: datetime,
    params: Params,
) -> Page[Task]:
    """Get tasks marked for deletion older than a given date.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    older_than : DateTime
        Date to compare.
    params : Params
        Pagination parameters.
    Returns
    -------
    List[Task]
        List of tasks older than the given date.
    """
    page = await apaginate(
        session,
        select(Task)
        .where(
            Task.deleted_at < older_than,
        )
        .order_by(Task.created_at),
        params,
    )
    return page


async def get_pending_tasks(
    session: AsyncSession,
    params: Params,
) -> Page[Task]:
    """Get all pending tasks.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    params : Params
        Pagination parameters.

    Returns
    -------
    Page[Task]
        List of pending tasks.
    """
    page = await apaginate(
        session,
        select(Task)
        .where(Task.status == TaskStatus.PENDING, Task.deleted_at.is_(None))
        .order_by(Task.created_at),
        params=params,
    )
    return page


async def get_active_tasks(session: AsyncSession, params: Params) -> Page[Task]:
    """Get all active tasks.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    params : Params
        Pagination parameters.

    Returns
    -------
    Page[Task]
        List of active tasks.
    """
    page = await apaginate(
        session,
        select(Task)
        .where(
            Task.status.notin_(
                [
                    TaskStatus.COMPLETED,
                    TaskStatus.CANCELLED,
                    TaskStatus.FAILED,
                ]
            ),
            Task.deleted_at.is_(None),
        )
        .order_by(Task.created_at),
        params=params,
    )
    return page


async def soft_delete_client_tasks(
    session: AsyncSession,
    client_id: str,
    ids: List[str] | None = None,
    inactive_only: bool = True,
) -> List[str]:
    """Soft delete tasks for a client.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    client_id : str
        Client ID.
    ids : List[str] | None
        Optional list of task IDs to delete.
    inactive_only : bool
        Delete only inactive tasks. Default is True.

    Returns
    -------
    List[str]
        List of task IDs that were soft-deleted.
    """
    filters: list[Any] = [
        Task.client_id == client_id,
        Task.deleted_at.is_(None),
    ]
    if ids:
        filters.append(Task.id.in_(ids))

    if inactive_only:
        filters.append(
            Task.status.in_(
                [
                    TaskStatus.COMPLETED,
                    TaskStatus.CANCELLED,
                    TaskStatus.FAILED,
                ]
            )
        )

    query = (
        update(Task)
        .where(*filters)
        .values(deleted_at=datetime.now(timezone.utc))
        .returning(Task.id)
    )
    result = await session.execute(query)
    await session.commit()
    deleted_ids = list(result.scalars())
    return deleted_ids


async def update_task_status(
    session: AsyncSession,
    task_id: str,
    status: TaskStatus,
    input_request_id: str | None = None,
    skip_results: bool = False,
    results: Dict[str, Any] | List[Dict[str, Any]] | None = None,
) -> None:
    """Update the status of a task.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    task_id : str
        Task ID.
    status : TaskStatus
        The task's status.
    input_request_id : str | None
        The task's input request ID if the status is WAITING_FOR_INPUT.
    skip_results : bool
        Skip updating the task's results.
        Default is False.
    results : Dict[str, Any] | List[Dict[str, Any]] | None
        The task's results.
        Default is None.
    """
    task = await get_task(session, task_id)
    if task is None:
        return
    task.status = status
    if skip_results is False:
        task.results = results
    if status == TaskStatus.WAITING_FOR_INPUT:
        task.input_request_id = input_request_id
    else:
        task.input_request_id = None
    task.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(task)


async def update_waiting_for_input_tasks(
    session: AsyncSession,
    older_than: datetime | None = None,
) -> None:
    """Update tasks waiting for input for more than 24 hours.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    older_than : DateTime
        Date to compare.
    """
    if older_than is None:
        older_than = datetime.now(timezone.utc) - timedelta(hours=24)
    # fmt: off
    await session.execute(
        update(Task)
        .where(
            Task.status == TaskStatus.WAITING_FOR_INPUT,
            Task.updated_at < older_than,
            Task.deleted_at.is_(None),
        )
        .values(status=TaskStatus.FAILED)
    )
    # fmt: on
    await session.commit()


async def delete_task(session: AsyncSession, task_id: str) -> None:
    """Delete a task from the database.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    task_id : str
        Task ID.
    """
    query = delete(Task).where(Task.id == task_id)
    await session.execute(query)
    await session.commit()


async def delete_client_tasks(session: AsyncSession, client_id: str) -> None:
    """Delete all tasks for a client.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    client_id : str
        Client ID.
    """
    query = delete(Task).where(Task.client_id == client_id)
    await session.execute(query)
    await session.commit()


async def delete_client_flow_task(
    session: AsyncSession, client_id: str, flow_id: str
) -> None:
    """Delete a task from the database.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    client_id : str
        Client ID.
    flow_id : str
        Flow ID.
    """
    query = delete(Task).where(
        Task.client_id == client_id,
        Task.flow_id == flow_id,
    )
    await session.execute(query)
    await session.commit()


async def count_active_tasks(session: AsyncSession) -> int:
    """Count active tasks.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.

    Returns
    -------
    int
        The number of active tasks.
    """
    count_query = select(sqlalchemy.sql.functions.count(Task.id)).where(
        Task.status.notin_(
            [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED]
        ),
        Task.deleted_at.is_(None),
    )
    result = await session.execute(count_query)
    return result.scalar_one()


async def count_pending_tasks(session: AsyncSession) -> int:
    """Count pending tasks.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.

    Returns
    -------
    int
        The number of pending tasks.
    """
    count_query = (
        select(sqlalchemy.sql.functions.count(Task.id))
        .select_from(Task)
        .where(Task.status == TaskStatus.PENDING, Task.deleted_at.is_(None))
    )
    result = await session.execute(count_query)
    return result.scalar_one()


async def mark_active_tasks_as_failed(session: AsyncSession) -> None:
    """Mark active tasks as failed.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    """
    await session.execute(
        update(Task)
        .where(
            Task.status.notin_(
                [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED]
            ),
            Task.deleted_at.is_(None),
        )
        .values(status=TaskStatus.FAILED)
    )
    await session.commit()


async def get_stuck_tasks(
    session: AsyncSession,
    params: Params,
) -> Page[Task]:
    """Get tasks that are marked as active but have results."

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    params : Params
        Pagination parameters.

    Returns
    -------
    Page[Task]
        List of tasks to check.
    """
    page = await apaginate(
        session,
        select(Task)
        .where(
            Task.status.notin_(
                [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED]
            ),
            Task.schedule_type.is_(None),
            Task.results.isnot(None),
            Task.deleted_at.is_(None),
        )
        .order_by(Task.created_at),
        params=params,
    )
    return page
