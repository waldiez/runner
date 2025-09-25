# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-param-doc,missing-yield-doc
# pylint: disable=unused-argument,protected-access,no-member
# pyright: reportPrivateUsage=false
"""Test waldiez_runner.routes.ws.validation*."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import WebSocket, WebSocketException
from starlette import status

from waldiez_runner.models.task import Task
from waldiez_runner.routes.ws.manager import TooManyClientsException
from waldiez_runner.routes.ws.registry import TooManyTasksException
from waldiez_runner.routes.ws.validation import (
    _validate_ws_connection,
    validate_websocket_connection,
    ws_task_registry,
)
from waldiez_runner.services import TaskService

MODULE_TO_PATCH = "waldiez_runner.routes.ws.validation"


@pytest.mark.asyncio
async def test_validate_websocket_connection_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test validate_websocket_connection."""
    websocket = AsyncMock(spec=WebSocket)
    fake_task = MagicMock(
        spec=Task, is_active=lambda: True, status=MagicMock(value="PENDING")
    )

    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.get_ws_client_id",
        AsyncMock(return_value=("client-123", "tasks-api")),
    )
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}._validate_ws_connection",
        AsyncMock(return_value=(fake_task, MagicMock())),
    )

    session = AsyncMock()
    settings = MagicMock()

    task, _manager, proto = await validate_websocket_connection(
        "task1", websocket, session, settings
    )
    assert proto == "tasks-api"
    assert task is fake_task


@pytest.mark.asyncio
async def test_validate_websocket_connection_missing_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test validate_websocket_connection with missing client ID."""
    websocket = AsyncMock(spec=WebSocket)
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.get_ws_client_id",
        AsyncMock(return_value=(None, None)),
    )

    with pytest.raises(WebSocketException) as err:
        await validate_websocket_connection(
            "task1", websocket, AsyncMock(), MagicMock()
        )

    assert err.value.code == status.WS_1008_POLICY_VIOLATION
    assert "Invalid client ID" in err.value.reason


@pytest.mark.asyncio
async def test_validate_websocket_connection_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test validate_websocket_connection with inactive task."""
    websocket = AsyncMock(spec=WebSocket)
    fake_task = MagicMock(
        spec=Task, is_active=lambda: False, status=MagicMock(value="finished")
    )

    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.get_ws_client_id",
        AsyncMock(return_value=("client-123", "sub-proto")),
    )
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}._validate_ws_connection",
        AsyncMock(return_value=(fake_task, MagicMock())),
    )

    with pytest.raises(WebSocketException) as err:
        await validate_websocket_connection(
            "task1", websocket, AsyncMock(), MagicMock()
        )

    assert "Task is not active" in err.value.reason


@pytest.mark.asyncio
async def test__validate_ws_connection_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _validate_ws_connection."""
    websocket = AsyncMock(spec=WebSocket)
    fake_task = MagicMock(spec=Task)
    fake_manager = MagicMock()
    fake_manager.add_client = MagicMock()

    monkeypatch.setattr(
        TaskService, "get_task", AsyncMock(return_value=fake_task)
    )
    monkeypatch.setattr(
        ws_task_registry,
        "get_or_create_task_manager",
        MagicMock(return_value=fake_manager),
    )

    task, _manager = await _validate_ws_connection(
        websocket, MagicMock(), "taskX"
    )
    assert task is fake_task
    fake_manager.add_client.assert_called_once_with(websocket)


@pytest.mark.asyncio
async def test__validate_ws_connection_task_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _validate_ws_connection with task not found."""
    monkeypatch.setattr(TaskService, "get_task", AsyncMock(return_value=None))
    with pytest.raises(WebSocketException) as err:
        await _validate_ws_connection(AsyncMock(), MagicMock(), "missing-task")
    assert "Task not found" in err.value.reason


@pytest.mark.asyncio
async def test__validate_ws_connection_too_many_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _validate_ws_connection with too many tasks."""
    monkeypatch.setattr(
        TaskService, "get_task", AsyncMock(return_value=MagicMock())
    )
    monkeypatch.setattr(
        ws_task_registry,
        "get_or_create_task_manager",
        MagicMock(side_effect=TooManyTasksException("Too many tasks")),
    )
    with pytest.raises(WebSocketException) as err:
        await _validate_ws_connection(AsyncMock(), MagicMock(), "taskY")
    assert "Too many tasks" in err.value.reason


@pytest.mark.asyncio
async def test__validate_ws_connection_too_many_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _validate_ws_connection with too many clients."""
    manager_mock = MagicMock()
    manager_mock.add_client = MagicMock(
        side_effect=TooManyClientsException("Too many clients")
    )

    monkeypatch.setattr(
        TaskService, "get_task", AsyncMock(return_value=MagicMock())
    )
    monkeypatch.setattr(
        ws_task_registry,
        "get_or_create_task_manager",
        MagicMock(return_value=manager_mock),
    )

    with pytest.raises(WebSocketException) as err:
        await _validate_ws_connection(AsyncMock(), MagicMock(), "taskZ")
    assert "Too many clients" in err.value.reason
