# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
#
# flake8: noqa: E501
# pylint: disable=missing-param-doc,missing-return-doc
# pylint: disable=missing-raises-doc,unused-argument
"""Test waldiez_runner.client._websockets.*."""

# import asyncio
import asyncio
import threading
import time
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from websockets import ConnectionClosed, InvalidStatus

from waldiez_runner.client._auth import CustomAuth
from waldiez_runner.client._websockets import (
    AsyncWebSocketClient,
    SyncWebSocketClient,
)


@patch("websockets.sync.client.connect")
def test_sync_send_message(
    mock_connect: MagicMock,
    auth: MagicMock,
) -> None:
    """Test synchronous message sending."""
    websocket_mock = MagicMock()
    mock_connect.return_value.__enter__.return_value = websocket_mock

    client = SyncWebSocketClient(auth=auth)
    client.send("task123", "hello")

    # Wait a moment for thread
    threading.Event().wait(1)

    websocket_mock.send.assert_called_with("hello")
    mock_connect.assert_called_once()


@patch("websockets.sync.client.connect")
def test_sync_listen_message(mock_connect: MagicMock, auth: MagicMock) -> None:
    """Test synchronous message listening."""
    ws_mock = MagicMock()
    ws_mock.recv.side_effect = ["test message", Exception("done")]
    mock_connect.return_value.__enter__.return_value = ws_mock

    received = []

    def on_msg(msg: Any) -> None:
        """Handle incoming messages."""
        received.append(msg)

    client = SyncWebSocketClient(auth=auth, reconnect=False)

    def run() -> None:
        """Run the client listen method."""
        client.listen("task123", on_msg, in_thread=False)

    t = threading.Thread(target=run)
    t.start()
    t.join(timeout=2)

    assert received == ["test message"]
    assert not client.is_listening()


@patch("websockets.sync.client.connect")
@patch("time.sleep", return_value=None)
def test_sync_listen_retries(
    mock_sleep: MagicMock,
    mock_connect: MagicMock,
    auth: CustomAuth,
) -> None:
    """Test that retries stop after max_retries is exceeded."""
    mock_connect.side_effect = Exception("fail")

    client = SyncWebSocketClient(auth=auth, reconnect=True, max_retries=2)
    errors: List[str] = []

    def on_error(err: str) -> None:
        """Handle errors."""
        errors.append(err)

    def run() -> None:
        """Run the client listen method."""
        client.listen(
            "task123",
            on_message=lambda x: None,
            on_error=on_error,
            in_thread=False,
        )

    t = threading.Thread(target=run)
    t.start()
    t.join(timeout=2)

    assert not t.is_alive(), "Thread did not exit"
    assert len(errors) == 1
    assert "fail" in errors[0]
    assert mock_connect.call_count == 3  # initial + 2 retries


@patch("websockets.sync.client.connect")
def test_sync_stop(mock_connect: MagicMock, auth: CustomAuth) -> None:
    """Test stopping the client from outside."""
    ws_mock = MagicMock()
    ws_mock.recv.side_effect = TimeoutError()
    mock_connect.return_value.__enter__.return_value = ws_mock

    client = SyncWebSocketClient(auth=auth)

    def run() -> None:
        """Run the client listen method."""
        client.listen("task123", on_message=lambda x: None, in_thread=True)

    run()
    time.sleep(0.2)
    client.stop()

    assert not client.is_listening()


@patch("websockets.sync.client.connect")
def test_sync_listen_1006_handled(
    mock_connect: MagicMock, auth: CustomAuth
) -> None:
    """Test 404 error is handled and stops the listener."""

    # pylint: disable=too-few-public-methods
    class FakeResponse:
        """Fake response for testing."""

        status_code = 1006

    class FakeInvalidStatus(InvalidStatus):
        """Fake InvalidStatus for testing."""

        def __init__(self) -> None:
            """Initialize the fake exception."""
            super().__init__(FakeResponse())  # type: ignore[arg-type]

    mock_connect.side_effect = FakeInvalidStatus()

    client = SyncWebSocketClient(auth=auth)
    errors: List[str] = []

    def on_error(err: str) -> None:
        """Handle errors."""
        errors.append(err)

    def run() -> None:
        """Run the client listen method."""
        client.listen(
            "task123",
            on_message=lambda x: None,
            on_error=on_error,
            in_thread=False,
        )

    t = threading.Thread(target=run)
    t.start()
    t.join(timeout=1)

    assert not t.is_alive()
    assert any("1006" in e or "InvalidStatus" in e for e in errors)


@patch("time.sleep", return_value=None)
@patch("websockets.sync.client.connect")
def test_sync_listen_1008_retry(
    mock_connect: MagicMock, auth: CustomAuth
) -> None:
    """Test that 1008 (auth error) causes a retry (token refresh)."""
    call_count = 0

    class FakeInvalidStatus(InvalidStatus):
        """Fake InvalidStatus for testing."""

        def __init__(self) -> None:
            """Initialize the fake exception."""
            super().__init__(None)  # type: ignore
            self.code = 1008

    def side_effect(*args: Any, **kwargs: Any) -> None:
        """Fake side effect for the mock."""
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise FakeInvalidStatus()
        # to force exit
        raise Exception("stop")  # pylint: disable=broad-exception-raised

    mock_connect.side_effect = side_effect

    client = SyncWebSocketClient(auth=auth, max_retries=2)
    errors: List[str] = []

    def run() -> None:
        """Run the client listen method."""
        client.listen(
            "task123",
            on_message=lambda x: None,
            on_error=errors.append,
            in_thread=False,
        )

    t = threading.Thread(target=run)
    t.start()
    t.join(timeout=2)

    assert not t.is_alive()
    assert call_count == 4


@patch("websockets.sync.client.connect")
def test_sync_stop_listening(
    mock_connect: MagicMock,
    auth: MagicMock,
) -> None:
    """Test stopping the listener."""
    ws_mock = MagicMock()
    ws_mock.recv.side_effect = [TimeoutError(), KeyboardInterrupt()]
    mock_connect.return_value.__enter__.return_value = ws_mock

    client = SyncWebSocketClient(auth=auth, max_retries=1)
    client.listen("task123", on_message=lambda x: None, in_thread=True)

    client.stop()
    assert not client.is_listening()


@pytest.mark.asyncio
@patch("websockets.asyncio.client.connect")
async def test_async_send_message(
    mock_connect: AsyncMock,
    auth: MagicMock,
) -> None:
    """Test async message sending."""
    ws_mock = AsyncMock()
    mock_connect.return_value.__aenter__.return_value = ws_mock

    client = AsyncWebSocketClient(auth=auth)
    await client.send("task123", "hello")

    ws_mock.send.assert_awaited_once_with("hello")


@pytest.mark.asyncio
@patch("websockets.asyncio.client.connect")
async def test_async_listen_in_task_true(
    mock_connect: AsyncMock,
    auth: CustomAuth,
) -> None:
    """Test listen with in_task=True using internal task management."""
    ws_mock = AsyncMock()
    ws_mock.recv = AsyncMock(side_effect=["message", Exception("done")])
    mock_connect.return_value.__aenter__.return_value = ws_mock

    received: List[str] = []

    async def on_msg(msg: str) -> None:
        """Handle incoming messages."""
        received.append(msg)

    client = AsyncWebSocketClient(auth=auth, reconnect=False)
    await client.listen("task123", on_message=on_msg, in_task=True)

    await asyncio.sleep(0.2)  # let it process one or two recv calls
    await client.stop()

    assert "message" in received
    assert not client.is_listening()


@pytest.mark.asyncio
@patch("websockets.asyncio.client.connect")
async def test_async_listen_in_task_false(
    mock_connect: AsyncMock,
    auth: CustomAuth,
) -> None:
    """Test listen using asyncio.create_task manually (not in_task=True)."""
    ws_mock = AsyncMock()
    ws_mock.recv = AsyncMock(side_effect=["message", Exception("done")])
    mock_connect.return_value.__aenter__.return_value = ws_mock

    received: List[str] = []

    async def on_msg(msg: str) -> None:
        """Handle incoming messages."""
        received.append(msg)

    client = AsyncWebSocketClient(auth=auth, reconnect=False)

    task = asyncio.create_task(client.listen("task123", on_msg, in_task=False))

    await asyncio.sleep(0.1)  # give it time to run once
    await client.stop()

    if not task.done():
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=1)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    assert received == ["message"]


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("websockets.asyncio.client.connect")
async def test_async_listen_retries(
    mock_connect: AsyncMock,
    mock_sleep: AsyncMock,
    auth: CustomAuth,
) -> None:
    """Test retries stop after exceeding max_retries."""
    mock_connect.side_effect = Exception("fail")

    client = AsyncWebSocketClient(auth=auth, reconnect=True, max_retries=2)
    errors: List[str] = []

    async def on_error(err: str) -> None:
        """Handle errors."""
        errors.append(err)

    await client.listen(
        "task123", on_message=AsyncMock(), on_error=on_error, in_task=False
    )

    assert len(errors) == 1
    assert "fail" in errors[0]
    assert mock_connect.call_count == 3


@pytest.mark.asyncio
@patch("websockets.asyncio.client.connect")
async def test_async_stop(
    mock_connect: AsyncMock,
    auth: CustomAuth,
) -> None:
    """Test stopping the async listener."""
    ws_mock = AsyncMock()
    ws_mock.recv.side_effect = [
        asyncio.TimeoutError(),
        ConnectionClosed(None, None),
    ]
    mock_connect.return_value.__aenter__.return_value = ws_mock

    client = AsyncWebSocketClient(auth=auth, reconnect=False)

    await client.listen("task123", on_message=AsyncMock())
    await asyncio.sleep(0.1)
    await client.stop()

    assert not client.is_listening()


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("websockets.asyncio.client.connect")
async def test_async_listen_1008_retry(
    mock_connect: AsyncMock,
    mock_sleep: AsyncMock,
    auth: CustomAuth,
) -> None:
    """Test that 1008 triggers token refresh and retry."""

    class FakeInvalidStatus(InvalidStatus):
        """Fake InvalidStatus for testing."""

        def __init__(self) -> None:
            """Initialize the fake exception."""
            super().__init__(None)  # type: ignore
            self.code = 1008

    mock_connect.side_effect = [
        FakeInvalidStatus(),  # 1008
        Exception("stop"),  # retry 1
        Exception("stop"),  # retry 2
        Exception("stop"),  # retry 3 → max_retries hit
    ]

    client = AsyncWebSocketClient(auth=auth, reconnect=True, max_retries=2)
    errors: List[str] = []

    async def on_error(err: str) -> None:
        """Handle errors."""
        errors.append(err)

    await client.listen(
        "task123", on_message=AsyncMock(), on_error=on_error, in_task=False
    )

    assert mock_connect.call_count == 4


@pytest.mark.asyncio
@patch("websockets.asyncio.client.connect")
async def test_async_listen_status_error(
    mock_connect: AsyncMock,
    auth: CustomAuth,
) -> None:
    """Test generic InvalidStatus error is passed to on_error."""

    # pylint: disable=too-few-public-methods
    class FakeResponse:
        """Fake response for testing."""

        status_code = 1006

    class FakeInvalidStatus(InvalidStatus):
        """Fake InvalidStatus for testing."""

        def __init__(self) -> None:
            """Initialize the fake exception."""
            super().__init__(FakeResponse())  # type: ignore[arg-type]

    mock_connect.side_effect = FakeInvalidStatus()

    client = AsyncWebSocketClient(auth=auth)
    errors: List[str] = []

    async def on_error(err: str) -> None:
        """Handle errors."""
        errors.append(err)

    await client.listen(
        "task123", on_message=AsyncMock(), on_error=on_error, in_task=False
    )

    assert any("1006" in e or "InvalidStatus" in e for e in errors)
