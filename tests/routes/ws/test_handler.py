# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-param-doc,missing-yield-doc
# pylint: disable=unused-argument,protected-access,no-member
# pyright: reportPrivateUsage=false, reportAttributeAccessIssue=false
# pyright: reportUnknownMemberType=false

"""Test waldiez_runner.routes.ws.handler*."""

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket, WebSocketException

from waldiez_runner.routes.ws.handler import (
    TaskWebSocketHandler,
    build_status_payload,
)
from waldiez_runner.routes.ws.listeners import (
    decode_stream_msg,
    listen_for_ws_input,
    valid_user_input,
)

MODULE_TO_PATCH = "waldiez_runner.routes.ws.handler"


@pytest.mark.asyncio
async def test_build_status_payload() -> None:
    """Test build_status_payload."""
    now = datetime.now(timezone.utc)
    task = MagicMock(
        id="task123",
        status=MagicMock(value="RUNNING"),
        created_at=now,
        updated_at=now,
        results={"a": "b"},
        input_request_id="req-1",
    )
    payload = build_status_payload(task)
    assert payload["type"] == "status"
    assert payload["data"]["task_id"] == "task123"
    assert payload["data"]["status"] == "RUNNING"
    assert payload["data"]["input_request_id"] == "req-1"
    assert isinstance(payload["data"]["created_at"], str)
    assert isinstance(payload["data"]["updated_at"], str)


@pytest.mark.asyncio
async def test_valid_user_input() -> None:
    """Test valid_user_input."""
    assert valid_user_input({"request_id": "abc", "data": "hello"})
    assert not valid_user_input({"request_id": 123, "data": "hello"})
    assert not valid_user_input("invalid")
    assert not valid_user_input({"foo": "bar"})


@pytest.mark.asyncio
async def test_decode_stream_msg() -> None:
    """Test decode_stream_msg."""
    raw = {b"type": b"log", b"data": b"hello"}
    msg = decode_stream_msg(raw, "1234-0")
    assert msg["type"] == "log"
    assert msg["data"] == "hello"
    assert msg["id"] == "1234-0"


@pytest.mark.asyncio
async def test_listen_for_ws_input_valid() -> None:
    """Test listen_for_ws_input with valid input."""
    mock_websocket = AsyncMock(spec=WebSocket)
    mock_websocket.receive_text = AsyncMock(
        side_effect=[
            json.dumps({"request_id": "abc", "data": "ok"}),
            asyncio.CancelledError(),
        ]
    )
    mock_websocket.send_json = AsyncMock()
    redis_mock = AsyncMock()

    with pytest.raises(asyncio.CancelledError):
        await listen_for_ws_input(
            mock_websocket, "test-channel", "task1", redis_mock
        )

    redis_mock.publish.assert_called_with(
        "test-channel", json.dumps({"request_id": "abc", "data": "ok"})
    )


@pytest.mark.asyncio
async def test_listen_for_ws_input_invalid() -> None:
    """Test listen_for_ws_input with invalid input."""
    mock_websocket = AsyncMock(spec=WebSocket)
    mock_websocket.receive_text = AsyncMock(
        side_effect=[
            json.dumps({"bad": "input"}),
            asyncio.CancelledError(),
        ]
    )
    mock_websocket.send_json = AsyncMock()
    redis_mock = AsyncMock()

    with pytest.raises(asyncio.CancelledError):
        await listen_for_ws_input(
            mock_websocket, "test-channel", "task1", redis_mock
        )

    mock_websocket.send_json.assert_called_with(
        {"error": "Invalid input payload"}
    )


# pylint: disable=too-few-public-methods
class FakeTask:
    """Fake task class for testing."""

    def __init__(self) -> None:
        """Initialize fake task."""
        self.id = "task1"
        self.status = MagicMock(value="RUNNING")
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.results = {}  # type: ignore
        self.input_request_id = "req1"


class FakeSettings:
    """Fake settings class for testing."""


@pytest.mark.asyncio
async def test_ws_handler_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test validate method with failure."""

    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.send_json = AsyncMock()

    redis_mock = AsyncMock()
    settings = FakeSettings()

    handler = TaskWebSocketHandler(
        websocket,
        "task1",
        settings,  # type: ignore
        redis_mock,
    )

    @asynccontextmanager
    async def fake_session_cm() -> AsyncGenerator[AsyncMock, None]:
        """Fake session context manager."""
        yield MagicMock()

    # Patch app_state.db
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.app_state.db",
        MagicMock(session=fake_session_cm),
    )

    # Patch validate_websocket_connection to raise error
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.validate_websocket_connection",
        AsyncMock(side_effect=Exception("fail")),
    )
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.ws_task_registry",
        MagicMock(
            get_or_create_task_manager=MagicMock(
                return_value=MagicMock(remove_client=MagicMock())
            )
        ),
    )

    with pytest.raises(WebSocketException):
        await handler.validate()


@pytest.mark.asyncio
async def test_ws_handler_send_initial_status_success() -> None:
    """Test send_initial_status method."""

    websocket = AsyncMock()
    websocket.send_json = AsyncMock()
    redis_mock = AsyncMock()

    handler = TaskWebSocketHandler(
        websocket,
        "task1",
        FakeSettings(),  # type: ignore
        redis_mock,
    )
    handler.task = FakeTask()  # type: ignore

    await handler._send_initial_status()
    assert websocket.send_json.call_count == 1


@pytest.mark.asyncio
async def test_ws_handler_cleanup() -> None:
    """Test cleanup method."""

    websocket = AsyncMock()
    task_manager = MagicMock()
    task_manager.clients = [websocket]

    redis_mock = AsyncMock()
    handler = TaskWebSocketHandler(
        websocket,
        "task1",
        FakeSettings(),  # type: ignore
        redis_mock,
    )
    handler.task_manager = task_manager

    with patch(
        f"{MODULE_TO_PATCH}.ws_task_registry.remove_task_if_empty"
    ) as mock_remove:
        handler._cleanup()
        task_manager.remove_client.assert_called_once_with(websocket)
        mock_remove.assert_called_once_with("task1")


@pytest.mark.asyncio
async def test_ws_handler_run_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test run method."""
    websocket = AsyncMock()
    redis = AsyncMock()
    handler = TaskWebSocketHandler(
        websocket,
        "task1",
        FakeSettings(),  # type: ignore
        redis,
    )

    monkeypatch.setattr(handler, "validate", AsyncMock())
    monkeypatch.setattr(handler, "_accept", AsyncMock())
    monkeypatch.setattr(handler, "_send_initial_status", AsyncMock())
    monkeypatch.setattr(handler, "_start_task_listeners", AsyncMock())
    monkeypatch.setattr(handler, "_cleanup", MagicMock())

    await handler.run()
    handler.validate.assert_awaited_once()  # type: ignore
    handler._accept.assert_awaited_once()  # type: ignore
    handler._send_initial_status.assert_awaited_once()  # type: ignore
    handler._start_task_listeners.assert_awaited_once()  # type: ignore
    handler._cleanup.assert_called_once()  # type: ignore


@pytest.mark.asyncio
async def test_ws_handler_run_with_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test run method with exception during accept."""
    websocket = AsyncMock()
    websocket.close = AsyncMock()
    redis = AsyncMock()
    handler = TaskWebSocketHandler(
        websocket,
        "task1",
        FakeSettings(),  # type: ignore
        redis,
    )

    monkeypatch.setattr(handler, "validate", AsyncMock())
    monkeypatch.setattr(
        handler,
        "_accept",
        AsyncMock(side_effect=WebSocketException(code=1008, reason="fail")),
    )
    monkeypatch.setattr(handler, "_cleanup", MagicMock())

    await handler.run()

    websocket.close.assert_awaited_once()
    handler._cleanup.assert_called_once()  # type: ignore


@pytest.mark.asyncio
async def test_ws_handler_accept_success() -> None:
    """Test _accept method."""
    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    handler = TaskWebSocketHandler(
        websocket,
        "taskX",
        FakeSettings(),  # type: ignore
        AsyncMock(),
    )
    handler.subprotocol = "tasks-api"

    await handler._accept()

    websocket.accept.assert_awaited_once_with(subprotocol="tasks-api")


@pytest.mark.asyncio
async def test_ws_handler_start_task_listeners_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _start_task_listeners method."""
    websocket = AsyncMock()
    redis = AsyncMock()
    manager = AsyncMock()

    handler = TaskWebSocketHandler(
        websocket,
        "task123",
        FakeSettings(),  # type: ignore
        redis,
    )
    handler.task_manager = manager

    # Patch task functions and wait
    monkeypatch.setattr(f"{MODULE_TO_PATCH}.listen_for_ws_input", AsyncMock())
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.stream_history_and_live", AsyncMock()
    )
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.asyncio.wait",
        AsyncMock(return_value=([MagicMock()], [])),
    )

    await handler._start_task_listeners()

    assert handler.input_task is not None
    assert handler.output_task is not None


@pytest.mark.asyncio
async def test_ws_handler_start_task_listeners_missing_manager() -> None:
    """Test _start_task_listeners with missing task manager."""
    websocket = AsyncMock()
    redis = AsyncMock()
    handler = TaskWebSocketHandler(
        websocket,
        "task123",
        FakeSettings(),  # type: ignore
        redis,
    )
    handler.task_manager = None

    with pytest.raises(WebSocketException, match="Task manager not found"):
        await handler._start_task_listeners()
