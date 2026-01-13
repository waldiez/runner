# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-param-doc,missing-yield-doc
# pylint: disable=unused-argument,protected-access,no-member
"""Test waldiez_runner.routes.ws.listeners.*."""

import asyncio
import json
from collections.abc import Coroutine
from typing import Any
from unittest.mock import AsyncMock, MagicMock

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
    manager = MagicMock()

    calls: list[dict[str, Any]] = []

    async def fake_broadcast(
        msg: dict[str, Any], skip_queue: bool = False
    ) -> None:
        calls.append(msg)

    manager.broadcast = fake_broadcast

    scheduled_tasks: list[Coroutine[None, None, None]] = []

    # Instead of returning the coroutine, we store it to run it ourselves
    def fake_create_task(
        coro: Coroutine[None, None, None],
    ) -> Coroutine[None, None, None]:
        """Fake create_task to store the coroutine."""
        scheduled_tasks.append(coro)
        return coro  # not awaited here! we await it later

    monkeypatch.setattr(
        f"{MODULE_TO_PATCH}.asyncio.create_task", fake_create_task
    )

    # Setup
    redis.xrevrange.return_value = [
        ("1-0", {b"type": b"log", b"data": b"history"})
    ]
    redis.xread.side_effect = [
        [
            (
                "stream",
                [
                    ("1-0", {b"type": b"log", b"data": b"dupe"}),  # skip
                    ("2-0", {b"type": b"log", b"data": b"live"}),
                ],
            )
        ],
        asyncio.CancelledError(),
    ]

    with pytest.raises(asyncio.CancelledError):
        await stream_history_and_live(redis, "stream", manager)

    for task in scheduled_tasks:
        await task

    assert len(calls) == 2
    assert any(msg["data"] == "history" for msg in calls)
    assert any(msg["data"] == "live" for msg in calls)
