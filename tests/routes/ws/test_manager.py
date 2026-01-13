# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-param-doc,unused-argument

"""Test waldiez_runner.routes.ws.manager.*."""

from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket

from waldiez_runner.routes.ws.manager import (
    TooManyClientsException,
    WsTaskManager,
)


@pytest.mark.anyio
async def test_add_client() -> None:
    """Test add_client."""
    manager = WsTaskManager(task_id="task_1", max_clients=2)
    manager.add_client(AsyncMock(spec=WebSocket))
    manager.add_client(AsyncMock(spec=WebSocket))
    with pytest.raises(TooManyClientsException):
        manager.add_client(AsyncMock(spec=WebSocket))


@pytest.mark.anyio
async def test_remove_client() -> None:
    """Test remove_client."""
    manager = WsTaskManager(task_id="task_1")
    ws1 = AsyncMock(spec=WebSocket)

    manager.add_client(ws1)
    manager.remove_client(ws1)

    assert len(manager.clients) == 0


@pytest.mark.anyio
async def test_broadcast() -> None:
    """Test broadcast."""
    manager = WsTaskManager(task_id="task_1")

    ws1, ws2 = AsyncMock(spec=WebSocket), AsyncMock(spec=WebSocket)
    manager.add_client(ws1)
    manager.add_client(ws2)

    await manager.broadcast({"type": "print", "data": "Hello"}, skip_queue=True)

    ws1.send_json.assert_awaited_once_with({"type": "print", "data": "Hello"})
    ws2.send_json.assert_awaited_once_with({"type": "print", "data": "Hello"})


@pytest.mark.anyio
async def test_is_empty() -> None:
    """Test is_empty."""
    manager = WsTaskManager(task_id="task_1")
    assert manager.is_empty() is True

    ws1 = AsyncMock(spec=WebSocket)
    manager.add_client(ws1)
    assert manager.is_empty() is False

    manager.remove_client(ws1)
    assert manager.is_empty() is True
