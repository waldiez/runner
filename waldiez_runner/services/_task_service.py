# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=line-too-long
"""Task management service."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Sequence

import sqlalchemy.sql.functions
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql.expression import cast, delete, update

from waldiez_runner.models.task import Task, TaskResponse
from waldiez_runner.models.task_status import TaskStatus


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


async def create_task(
    session: AsyncSession,
    client_id: str,
    flow_id: str,
    filename: str,
    input_timeout: int = 180,
) -> Task:
    """Create a new task in the database.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    client_id : str
        Client ID.
    flow_id : str
        Flow id.
    filename : str
        The task's entry point filename.
    input_timeout : int
        The timeout for input requests.
        Default is 180 seconds.

    Returns
    -------
    Task
        The created task.
    """
    task = Task(
        client_id=client_id,
        flow_id=flow_id,
        filename=filename,
        input_timeout=input_timeout,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


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
    query = select(Task).where(
        Task.id == task_id,
        cast(Task.deleted_at, DateTime).is_(None),
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_client_tasks(
    session: AsyncSession,
    client_id: str,
    params: Params,
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

    Returns
    -------
    Sequence[TaskResponse]
        List of tasks for the client.
    """

    page = await paginate(
        session,
        select(Task)
        .where(
            Task.client_id == client_id,
            cast(Task.deleted_at, DateTime).is_(None),
        )
        .order_by(Task.created_at),
        params=params,
        transformer=task_transformer,
    )
    return page


# async def get_client_flow_task(
#     session: AsyncSession, client_id: str, flow_id: str
# ) -> Task | None:
#     """Retrieve a task by client and flow ID.

#     Parameters
#     ----------
#     session : AsyncSession
#         SQLAlchemy async session.
#     client_id : str
#         Client ID.
#     flow_id : str
#         Flow ID.

#     Returns
#     -------
#     Task | None
#         Task instance or None if not found.
#     """
#     result = await session.execute(
#         select(Task).where(
#             Task.client_id == client_id,
#             Task.flow_id == flow_id,
#             cast(Task.deleted_at, DateTime).is_(None),
#         )
#     )
#     return result.scalar_one_or_none()


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
    page = await paginate(
        async_session,
        select(Task)
        .where(
            Task.client_id == client_id,
            Task.status.notin_(
                [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED]
            ),
            cast(Task.deleted_at, DateTime).is_(None),
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
    page = await paginate(
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
    page = await paginate(
        session,
        select(Task)
        .where(
            Task.status == TaskStatus.PENDING,
            cast(Task.deleted_at, DateTime).is_(None),
        )
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
    page = await paginate(
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
            cast(Task.deleted_at, DateTime).is_(None),
        )
        .order_by(Task.created_at),
        params=params,
    )
    return page


async def soft_delete_client_tasks(
    session: AsyncSession, client_id: str, inactive_only: bool = True
) -> List[str]:
    """Soft delete tasks for a client.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    client_id : str
        Client ID.
    inactive_only : bool
        Delete only inactive tasks. Default is True.

    Returns
    -------
    List[str]
        List of task IDs that were soft-deleted.
    """
    # use sqlalchemy's returning, to get the ids too.
    query = (
        update(Task)
        .where(
            Task.client_id == client_id,
            cast(Task.deleted_at, DateTime).is_(None),
        )
        .values(deleted_at=datetime.now(timezone.utc))
        .returning(Task.id)
    )
    if inactive_only:
        query = query.where(
            Task.status.in_(
                [
                    TaskStatus.COMPLETED,
                    TaskStatus.CANCELLED,
                    TaskStatus.FAILED,
                ]
            )
        )
    result = await session.execute(query)
    return list(result.scalars())


async def update_task_status(
    session: AsyncSession, task_id: str, new_status: TaskStatus
) -> None:
    """Update the status of a task.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    task_id : str
        Task ID.
    new_status : TaskStatus
        New status.
    """
    task = await get_task(session, task_id)
    if task is None:
        return
    task.status = new_status
    task.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(task)


async def update_task_results(
    session: AsyncSession,
    task_id: str,
    results: Dict[str, Any] | List[Dict[str, Any]] | None,
    status: TaskStatus,
) -> None:
    """Update the results of a task.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    task_id : str
        Task ID.
    results : str
        Task results.
    status : TaskStatus
        Task status.
    """
    task = await get_task(session, task_id)
    if task is None:
        return
    task.results = results
    task.status = status
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
        older_than = datetime.now() - timedelta(hours=24)
    # fmt: off
    await session.execute(
        update(Task)
        .where(
            Task.status == TaskStatus.WAITING_FOR_INPUT,
            Task.updated_at < older_than,
            cast(Task.deleted_at, DateTime).is_(None),
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
        cast(Task.deleted_at, DateTime).is_(None),
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
        .where(
            Task.status == TaskStatus.PENDING,
            cast(Task.deleted_at, DateTime).is_(None),
        )
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
            cast(Task.deleted_at, DateTime).is_(None),
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
    page = await paginate(
        session,
        select(Task)
        .where(
            Task.status.notin_(
                [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED]
            ),
            Task.results.isnot(None),
            cast(Task.deleted_at, DateTime).is_(None),
        )
        .order_by(Task.created_at),
        params=params,
    )
    return page
