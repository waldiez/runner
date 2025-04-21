# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-type-doc,missing-return-doc
# pylint: disable=missing-yield-doc

"""Tests for the TaskService."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi_pagination import Params
from sqlalchemy.ext.asyncio import AsyncSession

from waldiez_runner.models import TaskStatus
from waldiez_runner.services import _task_service as TaskService


@pytest.fixture(scope="function", name="pagination_params")
def pagination_params_fixture() -> Params:
    """Fixture for pagination params."""
    return Params(page=1, size=100)


@pytest.mark.anyio
async def test_create_task(async_session: AsyncSession) -> None:
    """Test task creation."""
    client_id = "test_create_task"
    task = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    assert task is not None
    assert task.client_id == client_id
    assert task.flow_id == "Sample Flow"
    assert task.status == TaskStatus.PENDING
    await TaskService.delete_task(async_session, task.id)


@pytest.mark.anyio
async def test_get_task(async_session: AsyncSession) -> None:
    """Test retrieving a task."""
    client_id = "test_get_task"
    created_task = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    await async_session.refresh(created_task)
    fetched_task = await TaskService.get_task(async_session, created_task.id)
    assert fetched_task is not None
    assert fetched_task.id == created_task.id
    assert fetched_task.client_id == client_id
    await TaskService.delete_task(async_session, fetched_task.id)


@pytest.mark.anyio
async def test_get_nonexistent_task(async_session: AsyncSession) -> None:
    """Test retrieving a non-existent task."""
    task_id = "test_get_nonexistent_task"
    fetched_task = await TaskService.get_task(async_session, task_id)
    assert fetched_task is None


@pytest.mark.anyio
async def test_update_task_status(async_session: AsyncSession) -> None:
    """Test updating task status."""
    client_id = "test_update_task_status"
    task = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
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
async def test_update_task_results(async_session: AsyncSession) -> None:
    """Test updating task results."""
    client_id = "test_update_task_results"
    task = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
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
async def test_delete_task(async_session: AsyncSession) -> None:
    """Test deleting a task."""
    client_id = "test_delete_task"
    task = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
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
async def test_get_active_client_task(async_session: AsyncSession) -> None:
    """Test getting an active client task."""
    client_id = "test_get_active_client_task"
    task = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
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
    async_session: AsyncSession, pagination_params: Params
) -> None:
    """Test getting all client tasks."""
    client_id = "test_get_client_tasks"
    task1 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    task2 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
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


@pytest.mark.anyio
async def test_get_no_client_tasks(
    async_session: AsyncSession, pagination_params: Params
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
async def test_delete_client_flow_task(async_session: AsyncSession) -> None:
    """Test deleting a client task."""
    client_id = "test_delete_client_flow_task"
    task = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    await TaskService.delete_client_flow_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
    )

    deleted_task = await TaskService.get_task(async_session, task.id)
    assert deleted_task is None

    # one more time just for branch coverage
    await TaskService.delete_client_flow_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
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


@pytest.mark.anyio
async def test_get_tasks_to_delete(
    async_session: AsyncSession, pagination_params: Params
) -> None:
    """Test getting tasks to delete."""
    client_id = "test_get_tasks_to_delete"
    task1 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    task2 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    task3 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    task1.mark_deleted()
    task2.mark_deleted()
    await async_session.commit()
    for task in (task1, task2, task3):
        await async_session.refresh(task)
    cutoff_time = datetime.now(timezone.utc) + timedelta(seconds=1)
    tasks_to_delete_page = await TaskService.get_tasks_to_delete(
        async_session,
        cutoff_time,
        params=pagination_params,
    )
    tasks_to_delete = tasks_to_delete_page.items
    all_ids = [task.id for task in tasks_to_delete]
    assert task1.id in all_ids
    assert task2.id in all_ids
    assert task3.id not in all_ids
    for task in (task1, task2, task3):
        await TaskService.delete_task(async_session, task.id)


@pytest.mark.anyio
async def test_get_pending_tasks(
    async_session: AsyncSession, pagination_params: Params
) -> None:
    """Test getting pending tasks."""
    client_id = "test_get_pending_tasks"
    task1 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    task2 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    task3 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
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
) -> None:
    """Test updating waiting for input tasks."""
    client_id = "test_update_waiting_for_input_tasks"
    task1 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    task2 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    task3 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    task4 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    task5 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
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
) -> None:
    """Test updating waiting for input tasks with no old tasks."""
    client_id = "test_update_waiting_for_input_tasks_no_old_tasks"
    task1 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="Sample Flow",
        filename="file1",
    )
    await TaskService.update_task_status(
        async_session, task1.id, TaskStatus.WAITING_FOR_INPUT
    )

    await TaskService.update_waiting_for_input_tasks(
        async_session,
        older_than=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    updated_task1 = await TaskService.get_task(async_session, task1.id)
    assert updated_task1 is not None
    assert updated_task1.status == TaskStatus.WAITING_FOR_INPUT
    await TaskService.delete_task(async_session, task1.id)


@pytest.mark.anyio
async def test_get_active_tasks(
    async_session: AsyncSession,
    pagination_params: Params,
) -> None:
    """Test getting active tasks."""
    client_id = "test_get_active_tasks"
    task1 = await TaskService.create_task(
        async_session,
        client_id=f"{client_id}1",
        flow_id="flow1",
        filename="file1",
    )
    task2 = await TaskService.create_task(
        async_session,
        client_id=f"{client_id}2",
        flow_id="flow2",
        filename="file1",
    )
    task3 = await TaskService.create_task(
        async_session,
        client_id=f"{client_id}3",
        flow_id="flow3",
        filename="file1",
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
) -> None:
    """Test deleting client tasks."""
    client_id = "test_delete_client_tasks"
    task1 = await TaskService.create_task(
        async_session, client_id=client_id, flow_id="flow1", filename="file1"
    )
    task2 = await TaskService.create_task(
        async_session, client_id=client_id, flow_id="flow2", filename="file1"
    )
    task3 = await TaskService.create_task(
        async_session,
        client_id=f"{client_id}1",
        flow_id="flow3",
        filename="file1",
    )
    await TaskService.delete_client_tasks(async_session, client_id=client_id)

    deleted_task1 = await TaskService.get_task(async_session, task1.id)
    deleted_task2 = await TaskService.get_task(async_session, task2.id)
    task3_in_db = await TaskService.get_task(async_session, task3.id)
    assert deleted_task1 is None
    assert deleted_task2 is None
    assert task3_in_db is not None


@pytest.mark.anyio
async def test_soft_delete_client_tasks(
    async_session: AsyncSession,
) -> None:
    """Test soft deleting client tasks."""
    client_id = "test_soft_delete_client_tasks"
    task1 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="flow1",
        filename="file1",
    )
    task1.status = TaskStatus.COMPLETED
    async_session.add(task1)
    await async_session.commit()
    task2 = await TaskService.create_task(
        async_session, client_id=client_id, flow_id="flow2", filename="file1"
    )
    task2.status = TaskStatus.FAILED
    async_session.add(task2)
    await async_session.commit()
    task3 = await TaskService.create_task(
        async_session,
        client_id=f"{client_id}1",
        flow_id="flow3",
        filename="file1",
    )
    await TaskService.soft_delete_client_tasks(
        async_session, client_id=client_id, inactive_only=True
    )

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
) -> None:
    """Test soft deleting client tasks without inactive_only."""
    client_id = "test_soft_delete_client_tasks_not_inactive_only"
    task1 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="flow1",
        filename="file1",
    )
    task1.status = TaskStatus.COMPLETED
    async_session.add(task1)
    await async_session.commit()
    task2 = await TaskService.create_task(
        async_session, client_id=client_id, flow_id="flow2", filename="file1"
    )
    task2.status = TaskStatus.FAILED
    async_session.add(task2)
    await async_session.commit()
    for task in (task1, task2):
        await async_session.refresh(task)

    task3 = await TaskService.create_task(
        async_session,
        client_id=f"{client_id}1",
        flow_id="flow3",
        filename="file1",
    )
    await TaskService.soft_delete_client_tasks(
        async_session, client_id=client_id, inactive_only=False
    )

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
) -> None:
    """Test ensuring only owned tasks are deleted."""
    client_id = "test_ensure_deleting_owned_only_tasks"
    task1 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="flow1",
        filename="file1",
    )
    task2 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="flow2",
        filename="file1",
    )
    task3 = await TaskService.create_task(
        async_session,
        client_id=f"{client_id}1",
        flow_id="flow3",
        filename="file1",
    )
    await TaskService.soft_delete_client_tasks(
        async_session,
        client_id=client_id,
        ids=[task1.id, task3.id],
        inactive_only=False,
    )

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
) -> None:
    """Test deleting client tasks with IDs."""
    client_id = "test_delete_client_tasks_with_ids"
    task1 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="flow1",
        filename="file1",
    )
    task2 = await TaskService.create_task(
        async_session, client_id=client_id, flow_id="flow2", filename="file1"
    )
    task3 = await TaskService.create_task(
        async_session,
        client_id=f"{client_id}1",
        flow_id="flow3",
        filename="file1",
    )
    await TaskService.soft_delete_client_tasks(
        async_session,
        client_id=client_id,
        ids=[task1.id],
        inactive_only=False,
    )

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
    async_session: AsyncSession, pagination_params: Params
) -> None:
    """Test getting stuck tasks."""
    client_id = "test_get_stuck_tasks"
    task1 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="flow1",
        filename="file1",
    )
    task2 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="flow2",
        filename="file1",
    )
    task3 = await TaskService.create_task(
        async_session,
        client_id=client_id,
        flow_id="flow3",
        filename="file1",
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
