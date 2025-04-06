# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-param-doc,missing-yield-doc
# pylint: disable=unused-argument,protected-access,no-member
"""Test waldiez_runner.routes.ws.listeners.*."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from waldiez_runner.routes.ws.listeners import (
    decode_stream_msg,
    listen_for_ws_input,
    stream_history_and_live,
    valid_user_input,
)

MODULE_TO_PATCH = "waldiez_runner.routes.ws.listeners"


@pytest.mark.asyncio
async def test_valid_user_input() -> None:
    """Test valid_user_input."""
    assert valid_user_input({"request_id": "abc", "data": "hello"})
    assert not valid_user_input({"request_id": 123, "data": "hello"})
    assert not valid_user_input("not-a-dict")
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
    websocket = AsyncMock(spec=WebSocket)
    websocket.receive_text = AsyncMock(
        side_effect=[
            json.dumps({"request_id": "abc", "data": "ok"}),
            asyncio.CancelledError(),
        ]
    )
    websocket.send_json = AsyncMock()
    redis_mock = AsyncMock()

    with pytest.raises(asyncio.CancelledError):
        await listen_for_ws_input(websocket, "chan", "task1", redis_mock)

    redis_mock.publish.assert_called_once_with(
        "chan", json.dumps({"request_id": "abc", "data": "ok"})
    )


@pytest.mark.asyncio
async def test_listen_for_ws_input_invalid() -> None:
    """Test listen_for_ws_input with invalid input."""
    websocket = AsyncMock(spec=WebSocket)
    websocket.receive_text = AsyncMock(
        side_effect=[
            json.dumps({"bad": "input"}),
            asyncio.CancelledError(),
        ]
    )
    websocket.send_json = AsyncMock()
    redis_mock = AsyncMock()

    with pytest.raises(asyncio.CancelledError):
        await listen_for_ws_input(websocket, "chan", "task1", redis_mock)

    websocket.send_json.assert_called_with({"error": "Invalid input payload"})


@pytest.mark.asyncio
async def test_listen_for_ws_input_disconnect() -> None:
    """Test listen_for_ws_input with WebSocketDisconnect."""
    websocket = AsyncMock(spec=WebSocket)
    websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
    redis_mock = AsyncMock()

    await listen_for_ws_input(websocket, "chan", "task1", redis_mock)
    # should log but not crash


@pytest.mark.asyncio
async def test_listen_for_ws_input_unexpected_error() -> None:
    """Test listen_for_ws_input with unexpected error."""
    websocket = AsyncMock(spec=WebSocket)
    websocket.receive_text = AsyncMock(side_effect=RuntimeError("boom"))
    redis_mock = AsyncMock()

    await listen_for_ws_input(websocket, "chan", "task1", redis_mock)
    # should log but not crash


@pytest.mark.asyncio
async def test_stream_history_and_live(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test stream_history_and_live."""
    redis = AsyncMock()
    manager = AsyncMock()

    # Setup: one historical msg, one duplicate, one live msg
    redis.xrevrange.return_value = [
        ("1-0", {b"type": b"log", b"data": b"history"})
    ]
    redis.xread.side_effect = [
        [
            (
                "stream",
                [
                    ("1-0", {b"type": b"log", b"data": b"dupe"}),
                    ("2-0", {b"type": b"log", b"data": b"live"}),
                ],
            )
        ],
        asyncio.CancelledError(),
    ]

    # Patch create_task to run coroutines directly
    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.asyncio.create_task", lambda coro: coro
    )

    with pytest.raises(asyncio.CancelledError):
        await stream_history_and_live(redis, "stream", manager)

    assert manager.broadcast.call_count == 2
    calls = [call.args[0]["data"] for call in manager.broadcast.call_args_list]
    assert "history" in calls
    assert "live" in calls
