# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-type-doc,missing-return-doc
# pylint: disable=missing-yield-doc

"""Tests for the TaskService."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi_pagination import Params
from sqlalchemy.ext.asyncio import AsyncSession

from tests.types import CreateTaskCallable
from waldiez_runner.models.task_status import TaskStatus
from waldiez_runner.schemas.task import TaskCreate
from waldiez_runner.services import TaskService


@pytest.fixture(scope="function", name="pagination_params")
def pagination_params_fixture() -> Params:
    """Fixture for pagination params."""
    return Params(page=1, size=100)


@pytest.mark.anyio
async def test_create_task(async_session: AsyncSession) -> None:
    """Test task creation."""
    client_id = "test_create_task"
    task_create = TaskCreate(
        client_id=client_id,
        flow_id="flow1",
        filename="file1.waldiez",
        input_timeout=180,
    )
    task = await TaskService.create_task(async_session, task_create)
    await async_session.commit()
    await async_session.refresh(task)
    assert task is not None
    assert task.client_id == client_id
    assert task.status == TaskStatus.PENDING
    await TaskService.delete_task(async_session, task.id)


@pytest.mark.anyio
async def test_get_task(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test retrieving a task."""
    client_id = "test_get_task"

    task, _ = await create_task(
        async_session,
        client_id=client_id,
    )
    fetched_task = await TaskService.get_task(async_session, task.id)
    assert fetched_task is not None
    assert fetched_task.id == task.id
    assert fetched_task.client_id == client_id
    await TaskService.delete_task(async_session, fetched_task.id)


@pytest.mark.anyio
async def test_get_nonexistent_task(async_session: AsyncSession) -> None:
    """Test retrieving a non-existent task."""
    task_id = "test_get_nonexistent_task"
    fetched_task = await TaskService.get_task(async_session, task_id)
    assert fetched_task is None


@pytest.mark.anyio
async def test_update_task_status(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test updating task status."""
    client_id = "test_update_task_status"
    task, _ = await create_task(
        async_session,
        client_id=client_id,
    )
    await TaskService.update_task_status(
        async_session, task.id, TaskStatus.RUNNING
    )
    await async_session.refresh(task)
    updated_task = await TaskService.get_task(async_session, task.id)
    assert updated_task is not None
    assert updated_task.status == TaskStatus.RUNNING
    await TaskService.delete_task(async_session, task.id)


@pytest.mark.anyio
async def test_update_nonexistent_task_status(
    async_session: AsyncSession,
) -> None:
    """Test updating task status to failed."""
    task_id = "test_update_nonexistent_task_status"
    await TaskService.update_task_status(
        async_session, task_id, TaskStatus.FAILED
    )  # Should complete without error


@pytest.mark.anyio
async def test_update_task_results(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test updating task results."""
    client_id = "test_update_task_results"
    task, _ = await create_task(
        async_session,
        client_id=client_id,
    )
    await TaskService.update_task_status(
        async_session,
        task.id,
        status=TaskStatus.COMPLETED,
        results={"results": "Test Results"},
    )
    await async_session.refresh(task)
    updated_task = await TaskService.get_task(async_session, task.id)
    assert updated_task is not None
    assert updated_task.results == {"results": "Test Results"}
    assert updated_task.status == TaskStatus.COMPLETED
    await TaskService.delete_task(async_session, task.id)


@pytest.mark.anyio
async def test_update_nonexistent_task_results(
    async_session: AsyncSession,
) -> None:
    """Test updating results of a non-existent task."""
    task_id = "nonexistent-id"
    await TaskService.update_task_status(
        async_session,
        task_id=task_id,
        results={"results": "Test Results"},
        status=TaskStatus.COMPLETED,
    )  # Should complete without error


@pytest.mark.anyio
async def test_delete_task(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test deleting a task."""
    client_id = "test_delete_task"
    task, _ = await create_task(
        async_session,
        client_id=client_id,
    )
    await TaskService.delete_task(async_session, task.id)

    deleted_task = await TaskService.get_task(async_session, task.id)
    assert deleted_task is None


@pytest.mark.anyio
async def test_delete_nonexistent_task(async_session: AsyncSession) -> None:
    """Test deleting a non-existent task (should not raise errors)."""
    task_id = "test_delete_nonexistent_task"
    await TaskService.delete_task(
        async_session, task_id=task_id
    )  # Should complete without error


@pytest.mark.anyio
async def test_get_active_client_task(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test getting an active client task."""
    client_id = "test_get_active_client_task"
    task, _ = await create_task(
        async_session,
        client_id=client_id,
    )
    await TaskService.update_task_status(
        async_session, task.id, TaskStatus.RUNNING
    )

    active_tasks = await TaskService.get_active_client_tasks(
        async_session,
        client_id=client_id,
    )
    assert task.id in [item.id for item in active_tasks.items]


@pytest.mark.anyio
async def test_get_nonexistent_active_client_tasks(
    async_session: AsyncSession,
) -> None:
    """Test getting a non-existent active client task."""
    client_id = "test_get_nonexistent_active_client_tasks"
    active_tasks = await TaskService.get_active_client_tasks(
        async_session,
        client_id=client_id,
    )
    assert not active_tasks.items


@pytest.mark.anyio
async def test_get_client_tasks(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
    pagination_params: Params,
) -> None:
    """Test getting all client tasks."""
    client_id = "test_get_client_tasks"
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    client_tasks = await TaskService.get_client_tasks(
        async_session,
        client_id=client_id,
        params=pagination_params,
    )
    all_ids = [task.id for task in client_tasks.items]
    assert task1.id in all_ids
    assert task2.id in all_ids
    await TaskService.delete_client_tasks(
        async_session,
        client_id=client_id,
    )


@pytest.mark.anyio
async def test_get_client_tasks_with_pagination(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
    pagination_params: Params,
) -> None:
    """Test getting client tasks with pagination."""
    client_id = "test_get_client_tasks_with_pagination"
    # noinspection DuplicatedCode
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file3",
    )
    task4, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file4",
    )
    pagination_params.page = 2
    pagination_params.size = 2
    client_tasks = await TaskService.get_client_tasks(
        async_session,
        client_id=client_id,
        params=pagination_params,
    )
    all_ids = [task.id for task in client_tasks.items]
    assert task3.id in all_ids
    assert task4.id in all_ids
    assert task1.id not in all_ids
    assert task2.id not in all_ids
    await TaskService.delete_client_tasks(
        async_session,
        client_id=client_id,
    )


@pytest.mark.anyio
async def test_get_client_tasks_with_search(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
    pagination_params: Params,
) -> None:
    """Test getting client tasks with search."""
    client_id = "test_get_client_tasks_with_search"
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file3",
    )
    client_tasks = await TaskService.get_client_tasks(
        async_session,
        client_id=client_id,
        params=pagination_params,
        search=task1.filename,
    )
    all_ids = [task.id for task in client_tasks.items]
    assert task1.id in all_ids
    assert task2.id not in all_ids
    assert task3.id not in all_ids
    await TaskService.delete_client_tasks(
        async_session,
        client_id=client_id,
    )


@pytest.mark.anyio
async def test_get_client_tasks_with_search_no_results(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
    pagination_params: Params,
) -> None:
    """Test getting client tasks with search and no results."""
    client_id = "test_get_client_tasks_with_search_no_results"
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file3",
    )
    client_tasks = await TaskService.get_client_tasks(
        async_session,
        client_id=client_id,
        params=pagination_params,
        search="nonexistent filename",
    )
    all_ids = [task.id for task in client_tasks.items]
    assert not all_ids
    assert task1.id not in all_ids
    assert task2.id not in all_ids
    assert task3.id not in all_ids


# noinspection DuplicatedCode
@pytest.mark.anyio
async def test_get_client_tasks_with_order(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
    pagination_params: Params,
) -> None:
    """Test getting client tasks with order."""
    client_id = "test_get_client_tasks_with_order"
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file3",
    )
    task4, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file4",
    )
    client_tasks = await TaskService.get_client_tasks(
        async_session,
        client_id=client_id,
        params=pagination_params,
        order_by="filename",
        descending=True,
    )
    assert client_tasks.items[0].filename == task4.filename
    assert client_tasks.items[1].filename == task3.filename
    assert client_tasks.items[2].filename == task2.filename
    assert client_tasks.items[3].filename == task1.filename

    acceding_client_tasks = await TaskService.get_client_tasks(
        async_session,
        client_id=client_id,
        params=pagination_params,
        order_by="filename",
        descending=False,
    )
    assert acceding_client_tasks.items[0].filename == task1.filename
    assert acceding_client_tasks.items[1].filename == task2.filename
    assert acceding_client_tasks.items[2].filename == task3.filename
    assert acceding_client_tasks.items[3].filename == task4.filename
    await TaskService.delete_client_tasks(
        async_session,
        client_id=client_id,
    )


@pytest.mark.anyio
async def test_get_no_client_tasks(
    async_session: AsyncSession,
    pagination_params: Params,
) -> None:
    """Test getting no client tasks."""
    client_id = "test_get_no_client_tasks"
    client_tasks = await TaskService.get_client_tasks(
        async_session,
        client_id=client_id,
        params=pagination_params,
    )
    assert not client_tasks.items


@pytest.mark.anyio
async def test_delete_client_flow_task(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test deleting a client task."""
    client_id = "test_delete_client_flow_task"
    task, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    await TaskService.delete_client_flow_task(
        async_session,
        client_id=client_id,
        flow_id=task.flow_id,
    )

    deleted_task = await TaskService.get_task(async_session, task.id)
    assert deleted_task is None

    # one more time just for branch coverage
    await TaskService.delete_client_flow_task(
        async_session,
        client_id=client_id,
        flow_id=task.flow_id,
    )


@pytest.mark.anyio
async def test_delete_nonexistent_client_flow_task(
    async_session: AsyncSession,
) -> None:
    """Test deleting a non-existent client task."""
    client_id = "test_delete_nonexistent_client_flow_task"
    await TaskService.delete_client_flow_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
    )  # Should complete without error


# noinspection DuplicatedCode
@pytest.mark.anyio
async def test_get_old_deleted_tasks(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test getting old tasks to delete."""
    client_id = "test_get_old_deleted_tasks"
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file3",
    )
    task1.mark_deleted()
    task2.mark_deleted()
    await async_session.commit()
    for task in (task1, task2, task3):
        await async_session.refresh(task)
    cutoff_time = datetime.now(timezone.utc) + timedelta(seconds=1)
    rows = await TaskService.get_old_tasks(
        async_session,
        cutoff_time,
        deleted=True,
        batch_size=100,
    )
    all_ids = [row.id for row in rows]
    assert task1.id in all_ids
    assert task2.id in all_ids
    assert task3.id not in all_ids
    await TaskService.delete_tasks(async_session, all_ids)


# noinspection DuplicatedCode
@pytest.mark.anyio
async def test_get_old_created_tasks(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test getting tasks to delete."""
    client_id = "test_get_old_created_tasks"
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file3",
    )
    task3.created_at = datetime.now(timezone.utc) + timedelta(seconds=10)
    await async_session.commit()
    for task in (task1, task2, task3):
        await async_session.refresh(task)
    cutoff_time = datetime.now(timezone.utc) + timedelta(seconds=1)
    rows = await TaskService.get_old_tasks(
        async_session,
        cutoff_time,
        deleted=False,
        batch_size=100,
    )
    all_ids = [row.id for row in rows]
    assert task1.id in all_ids
    assert task2.id in all_ids
    assert task3.id not in all_ids
    await TaskService.delete_tasks(async_session, all_ids)


@pytest.mark.anyio
async def test_get_pending_tasks(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
    pagination_params: Params,
) -> None:
    """Test getting pending tasks."""
    client_id = "test_get_pending_tasks"
    # noinspection DuplicatedCode
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file3",
    )
    await TaskService.update_task_status(
        async_session, task1.id, TaskStatus.PENDING
    )
    await TaskService.update_task_status(
        async_session, task2.id, TaskStatus.RUNNING
    )
    await TaskService.update_task_status(
        async_session, task3.id, TaskStatus.PENDING
    )
    pending_tasks_page = await TaskService.get_pending_tasks(
        async_session,
        params=pagination_params,
    )
    pending_tasks = pending_tasks_page.items
    assert len(pending_tasks) >= 2
    all_ids = [task.id for task in pending_tasks]
    assert task1.id in all_ids
    assert task2.id not in all_ids
    assert task3.id in all_ids


@pytest.mark.anyio
async def test_update_waiting_for_input_tasks(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test updating waiting for input tasks."""
    client_id = "test_update_waiting_for_input_tasks"
    # noinspection DuplicatedCode
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file3",
    )
    task4, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file4",
    )
    task5, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file5",
    )
    await TaskService.update_task_status(
        async_session, task1.id, TaskStatus.WAITING_FOR_INPUT
    )
    task2.mark_deleted()
    await async_session.commit()
    assert task2.is_inactive()
    await TaskService.update_task_status(
        async_session, task3.id, TaskStatus.WAITING_FOR_INPUT
    )
    await TaskService.update_task_status(
        async_session, task4.id, TaskStatus.WAITING_FOR_INPUT
    )
    task4.updated_at = datetime.now(timezone.utc) - timedelta(hours=25)
    await async_session.commit()

    # task1: waiting for input
    # task2: deleted
    # task3: waiting for input
    # task4: waiting for input, updated_at 25 hours ago
    # task5: pending
    await TaskService.update_waiting_for_input_tasks(async_session)
    updated_task1 = await TaskService.get_task(async_session, task1.id)
    updated_task2 = await TaskService.get_task(async_session, task2.id)
    updated_task3 = await TaskService.get_task(async_session, task3.id)
    updated_task4 = await TaskService.get_task(async_session, task4.id)
    updated_task5 = await TaskService.get_task(async_session, task5.id)
    assert updated_task1 is not None
    assert updated_task1.status == TaskStatus.WAITING_FOR_INPUT
    assert updated_task2 is None
    assert updated_task3 is not None
    assert updated_task3.status == TaskStatus.WAITING_FOR_INPUT
    assert updated_task4 is not None
    assert updated_task4.status == TaskStatus.FAILED
    assert updated_task5 is not None
    assert updated_task5.status == TaskStatus.PENDING
    for task_id in [task1.id, task2.id, task3.id, task4.id, task5.id]:
        await TaskService.delete_task(async_session, task_id)


@pytest.mark.anyio
async def test_update_waiting_for_input_tasks_no_old_tasks(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test updating waiting for input tasks with no old tasks."""
    client_id = "test_update_waiting_for_input_tasks_no_old_tasks"
    task, _ = await create_task(
        async_session,
        client_id=client_id,
    )
    await TaskService.update_task_status(
        async_session, task.id, TaskStatus.WAITING_FOR_INPUT
    )

    await TaskService.update_waiting_for_input_tasks(
        async_session,
        older_than=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    updated_task1 = await TaskService.get_task(async_session, task.id)
    assert updated_task1 is not None
    assert updated_task1.status == TaskStatus.WAITING_FOR_INPUT
    await TaskService.delete_task(async_session, task.id)


@pytest.mark.anyio
async def test_get_active_tasks(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
    pagination_params: Params,
) -> None:
    """Test getting active tasks."""
    client_id = "test_get_active_tasks"
    # noinspection DuplicatedCode
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file3",
    )
    await TaskService.update_task_status(
        async_session, task1.id, TaskStatus.FAILED
    )

    active_tasks_page = await TaskService.get_active_tasks(
        async_session,
        params=pagination_params,
    )
    active_tasks = active_tasks_page.items
    assert len(active_tasks) >= 2
    all_ids = [task.id for task in active_tasks]
    assert task1.id not in all_ids
    assert task2.id in all_ids
    assert task3.id in all_ids


@pytest.mark.anyio
async def test_delete_client_tasks(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test deleting client tasks."""
    client_id = "test_delete_client_tasks"
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=f"{client_id}1",
        filename="file3",
    )
    await TaskService.delete_client_tasks(async_session, client_id=client_id)

    # noinspection DuplicatedCode
    deleted_task1 = await TaskService.get_task(async_session, task1.id)
    deleted_task2 = await TaskService.get_task(async_session, task2.id)
    task3_in_db = await TaskService.get_task(async_session, task3.id)
    assert deleted_task1 is None
    assert deleted_task2 is None
    assert task3_in_db is not None


@pytest.mark.anyio
async def test_soft_delete_client_tasks(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test soft deleting client tasks."""
    client_id = "test_soft_delete_client_tasks"
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task1.status = TaskStatus.COMPLETED
    async_session.add(task1)
    await async_session.commit()
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task2.status = TaskStatus.FAILED
    async_session.add(task2)
    await async_session.commit()
    task3, _ = await create_task(
        async_session,
        client_id=f"{client_id}1",
        filename="file3",
    )
    await TaskService.soft_delete_client_tasks(
        async_session, client_id=client_id, inactive_only=True
    )

    # noinspection DuplicatedCode
    for task in (task1, task2, task3):
        await async_session.refresh(task)
    deleted_task1 = await TaskService.get_task(async_session, task1.id)
    deleted_task2 = await TaskService.get_task(async_session, task2.id)
    task3_in_db = await TaskService.get_task(async_session, task3.id)
    assert deleted_task1 is None
    assert deleted_task2 is None
    assert task3_in_db is not None
    assert task3_in_db.deleted_at is None


@pytest.mark.anyio
async def test_soft_delete_client_tasks_not_inactive_only(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test soft deleting client tasks without inactive_only."""
    client_id = "test_soft_delete_client_tasks_not_inactive_only"
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=f"{client_id}1",
        filename="file3",
    )
    task1.status = TaskStatus.COMPLETED
    async_session.add(task1)
    await async_session.commit()
    task2.status = TaskStatus.FAILED
    async_session.add(task2)
    await async_session.commit()
    for task in (task1, task2):
        await async_session.refresh(task)
    await TaskService.soft_delete_client_tasks(
        async_session, client_id=client_id, inactive_only=False
    )

    # noinspection DuplicatedCode
    deleted_task1 = await TaskService.get_task(async_session, task1.id)
    deleted_task2 = await TaskService.get_task(async_session, task2.id)
    task3_in_db = await TaskService.get_task(async_session, task3.id)
    assert deleted_task1 is None
    assert deleted_task2 is None
    assert task3_in_db is not None
    assert task3_in_db.deleted_at is None


@pytest.mark.anyio
async def test_ensure_deleting_owned_only_tasks(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test ensuring only owned tasks are deleted."""
    client_id = "test_ensure_deleting_owned_only_tasks"
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=f"{client_id}1",
        filename="file3",
    )
    await TaskService.soft_delete_client_tasks(
        async_session,
        client_id=client_id,
        ids=[task1.id, task3.id],
        inactive_only=False,
    )

    # noinspection DuplicatedCode
    for task in (task1, task2, task3):
        await async_session.refresh(task)
    deleted_task1 = await TaskService.get_task(async_session, task1.id)
    deleted_task2 = await TaskService.get_task(async_session, task2.id)
    task3_in_db = await TaskService.get_task(async_session, task3.id)
    assert deleted_task1 is None
    assert deleted_task2 is not None
    assert task3_in_db is not None
    assert task3_in_db.deleted_at is None
    await TaskService.soft_delete_client_tasks(
        async_session,
        client_id=client_id,
    )


@pytest.mark.anyio
async def test_delete_client_tasks_with_ids(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
) -> None:
    """Test deleting client tasks with IDs."""
    client_id = "test_delete_client_tasks_with_ids"
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=f"{client_id}1",
        filename="file3",
    )
    await TaskService.soft_delete_client_tasks(
        async_session,
        client_id=client_id,
        ids=[task1.id],
        inactive_only=False,
    )

    # noinspection DuplicatedCode
    for task in (task1, task2, task3):
        await async_session.refresh(task)
    deleted_task1 = await TaskService.get_task(async_session, task1.id)
    deleted_task2 = await TaskService.get_task(async_session, task2.id)
    task3_in_db = await TaskService.get_task(async_session, task3.id)
    assert deleted_task1 is None
    assert deleted_task2 is not None
    assert task3_in_db is not None
    assert task3_in_db.deleted_at is None
    await TaskService.soft_delete_client_tasks(
        async_session, client_id=client_id
    )


@pytest.mark.anyio
async def test_get_stuck_tasks(
    async_session: AsyncSession,
    create_task: CreateTaskCallable,
    pagination_params: Params,
) -> None:
    """Test getting stuck tasks."""
    client_id = "test_get_stuck_tasks"
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file2",
    )
    task3, _ = await create_task(
        async_session,
        client_id=client_id,
        filename="file3",
    )
    task1.results = {"results": "Test Results"}
    task2.results = {"results": "Test Results"}
    await async_session.commit()
    for task in (task1, task2, task3):
        await async_session.refresh(task)

    stuck_tasks_page = await TaskService.get_stuck_tasks(
        async_session,
        params=pagination_params,
    )
    stuck_tasks = stuck_tasks_page.items
    assert len(stuck_tasks) >= 2
    assert task1.id in [task.id for task in stuck_tasks]
    assert task2.id in [task.id for task in stuck_tasks]
    assert task3.id not in [task.id for task in stuck_tasks]
