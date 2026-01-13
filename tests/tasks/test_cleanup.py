# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-type-doc,missing-return-doc
# pylint: disable=missing-yield-doc

"""Tests for the cleanup functions in the tasks module."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from waldiez_runner.tasks.cleanup import delete_task

CLEANUP_MODULE = "waldiez_runner.tasks.cleanup"


@pytest.mark.asyncio
@patch(
    f"{CLEANUP_MODULE}.TaskService.delete_task",
    new_callable=AsyncMock,
)
async def test_delete_task(mock_delete_task: AsyncMock) -> None:
    """Test deleting a single task."""
    mock_storage = AsyncMock()

    # noinspection PyTypeChecker
    await delete_task(
        task_id="task1",
        client_id="client1",
        db_manager=MagicMock(),
        storage=mock_storage,
    )

    mock_delete_task.assert_awaited_once()
    folder_path = os.path.join("client1", "task1")
    mock_storage.delete_folder.assert_awaited_once_with(folder_path)
