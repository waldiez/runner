# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-type-doc,missing-return-doc
# pylint: disable=unused-argument,line-too-long
"""Test waldiez_runner.tasks.schedule module."""

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis
import pytest
from fastapi_pagination import Page, Params

from waldiez_runner.models import Task, TaskStatus
from waldiez_runner.tasks.schedule import (
    check_stuck_tasks,
    cleanup_old_tasks,
    cleanup_processed_requests,
    heartbeat,
    trim_old_stream_entries,
)

SCHEDULE_MODULE = "waldiez_runner.tasks.schedule"


@pytest.mark.asyncio
@patch(f"{SCHEDULE_MODULE}.TaskService.delete_task", new_callable=AsyncMock)
@patch(
    f"{SCHEDULE_MODULE}.TaskService.get_tasks_to_delete", new_callable=AsyncMock
)
async def test_cleanup_old_tasks(
    mock_get_tasks_to_delete: AsyncMock,
    mock_delete_task: AsyncMock,
) -> None:
    """Test cleaning up old tasks."""
    mock_storage = MagicMock()
    mock_db_session = AsyncMock()

    async def get_tasks_to_delete(*args: Any, **kwargs: Any) -> Page[Task]:
        """Return tasks to delete."""
        default_params = Params(page=1, size=100)
        params = kwargs.get("params", default_params)
        if not isinstance(params, Params):
            params = default_params
        if params.page == 1:
            return Page(
                items=[
                    Task(
                        id="get_tasks_to_delete1",
                        client_id="client1",
                        created_at="2024-01-01T00:00:00",
                        updated_at="2024-01-01T00:00:00",
                    ),
                    Task(
                        id="get_tasks_to_delete2",
                        client_id="client2",
                        created_at="2024-02-01T00:00:00",
                        updated_at="2024-01-01T00:00:00",
                    ),
                ],
                page=1,
                size=100,
                total=2,
            )
        return Page(items=[], page=1, size=100, total=0)

    mock_get_tasks_to_delete.side_effect = get_tasks_to_delete

    mock_delete_folder = AsyncMock()
    mock_storage.delete_folder = mock_delete_folder

    await cleanup_old_tasks(db_session=mock_db_session, storage=mock_storage)

    assert mock_get_tasks_to_delete.await_count == 2

    assert mock_delete_task.await_count == 2
    task1_path = os.path.join("client1", "get_tasks_to_delete1")
    task2_path = os.path.join("client2", "get_tasks_to_delete2")
    mock_delete_folder.assert_any_await(task1_path)
    mock_delete_folder.assert_any_await(task2_path)


@pytest.mark.asyncio
@patch(
    f"{SCHEDULE_MODULE}.TaskService.update_task_status", new_callable=AsyncMock
)
@patch(f"{SCHEDULE_MODULE}.TaskService.get_stuck_tasks", new_callable=AsyncMock)
async def test_check_stuck_tasks(
    mock_get_stuck_tasks: AsyncMock,
    mock_update_task_status: AsyncMock,
) -> None:
    """Test checking stuck tasks."""
    mock_storage = MagicMock()
    mock_db_session = AsyncMock()

    async def get_stuck_tasks(*args: Any, **kwargs: Any) -> Page[Task]:
        """Return tasks to check."""
        default_params = Params(page=1, size=100)
        params = kwargs.get("params", default_params)
        if not isinstance(params, Params):
            params = default_params
        if params.page == 1:
            return Page(
                items=[
                    Task(
                        id="test_check_stuck_tasks1",
                        client_id="client1",
                        created_at="2024-01-01T00:00:00",
                        updated_at="2024-01-01T00:00:00",
                        results={"key": "value"},
                    ),
                    Task(
                        id="test_check_stuck_tasks2",
                        client_id="client2",
                        created_at="2024-02-01T00:00:00",
                        updated_at="2024-01-01T00:00:00",
                        results=None,
                    ),
                    Task(
                        id="test_check_stuck_tasks3",
                        client_id="client3",
                        created_at="2024-01-01T00:00:00",
                        updated_at="2024-01-01T00:00:00",
                        results={"key": "value"},
                    ),
                    Task(
                        id="test_check_stuck_tasks4",
                        client_id="client4",
                        created_at="2024-02-01T00:00:00",
                        updated_at="2024-01-01T00:00:00",
                        results={"error": "Something went wrong"},
                    ),
                ],
                page=1,
                size=100,
                total=3,
            )
        return Page(items=[], page=1, size=100, total=0)

    async def list_files(folder_path: str) -> list[str]:
        """List files in a folder."""
        if folder_path == os.path.join("client3", "test_check_stuck_tasks3"):
            return ["file1"]
        return []

    mock_list_files = AsyncMock(side_effect=list_files)
    mock_storage.list_files = mock_list_files
    mock_get_stuck_tasks.side_effect = get_stuck_tasks

    await check_stuck_tasks(db_session=mock_db_session, storage=mock_storage)

    assert mock_get_stuck_tasks.await_count == 2
    assert mock_update_task_status.await_count == 4
    assert mock_list_files.await_count == 2
    # the other two tasks return early (before listing files)
    task1_path = os.path.join("client1", "test_check_stuck_tasks1")
    task3_path = os.path.join("client3", "test_check_stuck_tasks3")
    mock_list_files.assert_any_await(task1_path)
    mock_list_files.assert_any_await(task3_path)
    # mock_list_files.assert_any_await("client1/test_check_stuck_tasks1")
    # mock_list_files.assert_any_await("client3/test_check_stuck_tasks3")

    # no files
    mock_update_task_status.assert_any_await(
        mock_db_session,
        task_id="test_check_stuck_tasks1",
        status=TaskStatus.FAILED,
        skip_results=True,
    )
    # results=None
    mock_update_task_status.assert_any_await(
        mock_db_session,
        task_id="test_check_stuck_tasks2",
        status=TaskStatus.FAILED,
        skip_results=True,
    )
    # results dict, (no "error" key) and files
    mock_update_task_status.assert_any_await(
        mock_db_session,
        task_id="test_check_stuck_tasks3",
        status=TaskStatus.COMPLETED,
        skip_results=True,
    )
    # results dict with "error" key
    mock_update_task_status.assert_any_await(
        mock_db_session,
        task_id="test_check_stuck_tasks4",
        status=TaskStatus.FAILED,
        skip_results=True,
    )


@pytest.mark.asyncio
@patch(
    f"{SCHEDULE_MODULE}.RedisIOStream.a_cleanup_processed_requests"  # noqa: E501
)
async def test_cleanup_processed_requests(
    mock_cleanup: AsyncMock,
) -> None:
    """Test cleaning up processed requests."""
    mock_redis = AsyncMock()
    await cleanup_processed_requests(redis=mock_redis)
    mock_cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_trim_old_stream_entries(
    a_fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """Test trimming old stream entries."""
    stream_name = "task:test_trim_old_stream_entries:output"
    for i in range(10):
        await a_fake_redis.xadd(stream_name, {"key": f"value{i}"})
    assert await a_fake_redis.xlen(stream_name) == 10
    await trim_old_stream_entries(redis=a_fake_redis, maxlen=5)
    assert await a_fake_redis.xlen(stream_name) == 5


@pytest.mark.asyncio
@patch(f"{SCHEDULE_MODULE}.LOG.info")
async def test_heartbeat(mock_log: MagicMock) -> None:
    """Test simple heartbeat."""
    await heartbeat()
    mock_log.assert_called_once_with("Heartbeat")
