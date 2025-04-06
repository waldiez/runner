# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-param-doc,unused-argument

"""Test waldiez_runner.routes.ws.registry.*."""

import time
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket

from waldiez_runner.routes.ws.manager import WsTaskManager
from waldiez_runner.routes.ws.registry import (
    TooManyTasksException,
    WsTaskRegistry,
)


def test_get_or_create_task_manager() -> None:
    """Test get_or_create_task_manager."""
    registry = WsTaskRegistry(max_active_tasks=2)

    registry.get_or_create_task_manager("task_1")
    registry.get_or_create_task_manager("task_2")
    with pytest.raises(TooManyTasksException):
        registry.get_or_create_task_manager("task_3")


def test_remove_task_if_empty() -> None:
    """Test remove_task_if_empty."""
    registry = WsTaskRegistry()
    manager = registry.get_or_create_task_manager("task_1")
    assert "task_1" in registry.tasks

    manager.clients = []
    registry.remove_task_if_empty("task_1")

    assert "task_1" not in registry.tasks


def test_existing_task_manager() -> None:
    """Test that the same task manager is returned for the same task ID."""
    registry = WsTaskRegistry()
    manager1 = registry.get_or_create_task_manager("task_1")
    manager2 = registry.get_or_create_task_manager("task_1")

    assert manager1 is manager2


def test_stats() -> None:
    """Test stats."""
    registry = WsTaskRegistry()
    registry.get_or_create_task_manager("task_1")
    registry.get_or_create_task_manager("task_2")

    stats = registry.stats()
    assert stats == {
        "active_tasks": 2,
        "connected_clients": 0,
        "per_task": {"task_1": 0, "task_2": 0},
    }


def test_expire_idle_tasks() -> None:
    """Test expire_idle_tasks."""
    registry = WsTaskRegistry()
    registry.get_or_create_task_manager("task_1")
    registry.get_or_create_task_manager("task_2")

    time.sleep(0.5)

    registry.tasks["task_2"].update_usage()

    registry.expire_idle_tasks(max_idle_seconds=0.2)

    assert "task_1" not in registry.tasks
    assert "task_2" in registry.tasks


@pytest.mark.anyio
async def test_broadcast_to() -> None:
    """Test broadcast_to."""
    ws = AsyncMock(spec=WebSocket)
    manager = WsTaskManager(task_id="task_1")
    manager.add_client(ws)
    registry = WsTaskRegistry()
    registry.tasks["task_1"] = manager

    # with skip_queue=True
    await registry.broadcast_to(
        "task_1", {"type": "print", "data": "World"}, skip_queue=True
    )
    ws.send_json.assert_awaited_once_with({"type": "print", "data": "World"})
