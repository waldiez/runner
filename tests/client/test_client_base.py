# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pylint: disable=missing-param-doc,missing-return-doc
# pylint: disable=protected-access,unused-argument
# pyright: reportPrivateUsage=false,reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false

"""Test waldiez_runner.client._client_base.*."""

import asyncio
from collections.abc import Coroutine
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from waldiez_runner.client.auth import Auth
from waldiez_runner.client.client_base import BaseClient
from waldiez_runner.client.models import StatusResponse


@pytest.fixture(name="base_client")
def base_client_fixture() -> BaseClient:
    """Return a new BaseClient instance."""
    return BaseClient()


def test_configure_sets_auth_and_handlers() -> None:
    """Test that configure sets the auth and handlers correctly."""

    # noinspection PyUnusedLocal
    def token_cb(token: str) -> None:
        """Token callback."""

    # noinspection PyUnusedLocal
    def error_cb(msg: str) -> None:
        """Error callback."""

    client = BaseClient()
    client.configure(
        base_url="http://localhost",
        client_id="abc",
        client_secret="secret",  # nosemgrep # nosec
        on_auth_token=token_cb,
        on_auth_error=error_cb,
        on_error=error_cb,
    )
    assert client.auth is not None
    # pylint: disable=comparison-with-callable
    assert client.on_auth_token == token_cb
    assert client.on_auth_error == error_cb
    assert client.on_error == error_cb


# noinspection PyUnusedLocal
def test_has_valid_token_true(mocker: MockerFixture) -> None:
    """Test that has_valid_token returns True when auth is valid."""
    client = BaseClient()
    mock_auth = MagicMock()
    mock_auth.has_valid_token.return_value = True
    client.auth = mock_auth
    assert client.has_valid_token()


def test_has_valid_token_false() -> None:
    """Test that has_valid_token returns False when auth is invalid."""
    client = BaseClient()
    client.auth = None
    assert not client.has_valid_token()


# noinspection PyUnusedLocal
def test_authenticate_success(mocker: MockerFixture) -> None:
    """Test that authenticate returns True when auth is successful."""
    client = BaseClient()
    client.auth = MagicMock()
    client.auth.base_url = "url"
    client.auth.client_id = "id"
    client.auth.client_secret = "secret"  # nosemgrep # nosec
    client.auth.sync_get_token = MagicMock()
    assert client.authenticate()


# noinspection PyUnusedLocal
def test_authenticate_failure(mocker: MockerFixture) -> None:
    """Test that authenticate returns False when auth fails."""
    client = BaseClient()
    client.auth = MagicMock()
    client.auth.base_url = "url"
    client.auth.client_id = "id"
    client.auth.client_secret = "secret"  # nosemgrep # nosec
    client.auth.sync_get_token.side_effect = Exception("fail")
    client._handle_auth_error = MagicMock()  # type: ignore
    assert not client.authenticate()
    client._handle_auth_error.assert_called_once()


# noinspection PyUnusedLocal
@pytest.mark.anyio
async def test_a_authenticate_success(mocker: MockerFixture) -> None:
    """Test that a_authenticate returns True when auth is successful."""
    client = BaseClient()
    client.auth = MagicMock()
    client.auth.base_url = "url"
    client.auth.client_id = "id"
    client.auth.client_secret = "secret"  # nosemgrep # nosec
    client.auth.async_get_token = AsyncMock()
    assert await client.a_authenticate()


# noinspection PyUnusedLocal
@pytest.mark.anyio
async def test_a_authenticate_failure(mocker: MockerFixture) -> None:
    """Test that a_authenticate returns False when auth fails."""
    client = BaseClient()
    client.auth = MagicMock()
    client.auth.base_url = "url"
    client.auth.client_id = "id"
    client.auth.client_secret = "secret"  # nosemgrep # nosec
    client.auth.async_get_token.side_effect = Exception("fail")
    client._handle_auth_error = MagicMock()  # type: ignore
    assert not await client.a_authenticate()
    client._handle_auth_error.assert_called_once()


# Dummy loop for async task scheduling
# pylint: disable=too-few-public-methods,no-self-use
# noinspection PyMethodMayBeStatic
class DummyLoop:
    """Dummy loop for async task scheduling."""

    def create_task(self, coro: Coroutine[Any, Any, None]) -> None:
        """Create a task."""
        asyncio.get_event_loop().run_until_complete(coro)


def test_context_manager_sync() -> None:
    """Test that the context manager works for sync clients."""
    client = BaseClient(
        base_url="http://localhost",
        client_id="id",
        client_secret="secret",  # nosemgrep # nosec
    )
    with client as c:
        assert c is client


@pytest.mark.anyio
async def test_context_manager_async() -> None:
    """Test that the context manager works for async clients."""
    client = BaseClient(
        base_url="http://localhost",
        client_id="id",
        client_secret="secret",  # nosemgrep # nosec
    )
    async with client as c:
        assert c is client


def test_handle_auth_error_sync() -> None:
    """Test that handle_auth_error calls the callback."""
    called: list[str] = []

    def cb(msg: str) -> None:
        """Callback."""
        called.append(msg)

    client = BaseClient(on_auth_error=cb)
    client._handle_auth_error("fail")
    assert called == ["fail"]


def test_handle_auth_error_async_create_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that handle_auth_error calls the callback."""
    called: list[str] = []

    async def cb(msg: str) -> None:
        """Async callback."""
        called.append(msg)

    def dummy_get_running_loop() -> DummyLoop:
        """Dummy get_running_loop."""
        return DummyLoop()

    monkeypatch.setattr(asyncio, "get_running_loop", dummy_get_running_loop)
    client = BaseClient(on_auth_error=cb)
    client._handle_auth_error("fail")
    assert called == ["fail"]


# noinspection DuplicatedCode
def test_handle_auth_error_async_fallback_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that handle_auth_error calls the callback."""
    called: list[str] = []

    async def cb(msg: str) -> None:
        """Async callback."""
        called.append(msg)

    monkeypatch.setattr(
        asyncio,
        "get_running_loop",
        lambda: (_ for _ in ()).throw(RuntimeError()),
    )
    monkeypatch.setattr(
        asyncio,
        "run",
        lambda coro: asyncio.get_event_loop().run_until_complete(coro),
    )
    client = BaseClient(on_auth_error=cb)
    client._handle_auth_error("fail")
    assert called == ["fail"]


def test_handle_error_sync() -> None:
    """Test that handle_error calls the callback."""
    called: list[str] = []

    def cb(msg: str) -> None:
        """Callback."""
        called.append(msg)

    client = BaseClient(on_error=cb)
    client._handle_error("fail")
    assert called == ["fail"]


def test_handle_error_async_create_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that handle_error calls the callback."""
    called: list[str] = []

    async def cb(msg: str) -> None:
        """Async callback."""
        called.append(msg)

    def dummy_get_running_loop() -> DummyLoop:
        """Dummy get_running_loop."""
        return DummyLoop()

    monkeypatch.setattr(asyncio, "get_running_loop", dummy_get_running_loop)
    client = BaseClient(on_error=cb)
    client._handle_error("fail")
    assert called == ["fail"]


# noinspection DuplicatedCode
def test_handle_error_async_fallback_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that handle_error calls the callback."""
    called: list[str] = []

    async def cb(msg: str) -> None:
        """Async callback."""
        called.append(msg)

    monkeypatch.setattr(
        asyncio,
        "get_running_loop",
        lambda: (_ for _ in ()).throw(RuntimeError()),
    )
    monkeypatch.setattr(
        asyncio,
        "run",
        lambda coro: asyncio.get_event_loop().run_until_complete(coro),
    )
    client = BaseClient(on_error=cb)
    client._handle_error("fail")
    assert called == ["fail"]


def test_ensure_configured_raises_if_not_configured() -> None:
    """Test that _ensure_configured raises ValueError if not configured."""
    client = BaseClient()
    with pytest.raises(ValueError):
        client._ensure_configured()


# noinspection DuplicatedCode
def test_get_status_success(httpx_mock: HTTPXMock, auth: Auth) -> None:
    """Test get_status returns valid StatusResponse on success."""

    httpx_mock.add_response(
        method="GET",
        url=f"{auth.base_url}/status",
        json={
            "healthy": True,
            "active_tasks": 2,
            "pending_tasks": 1,
            "max_capacity": 4,
            "cpu_count": 8,
            "cpu_percent": 35.5,
            "total_memory": 16000000000,
            "used_memory": 8000000000,
            "memory_percent": 50,
        },
        status_code=200,
    )

    client = BaseClient()
    client.configure(
        base_url=auth.base_url,  # type: ignore
        client_id=auth.client_id,  # type: ignore
        client_secret=auth.client_secret,  # type: ignore
    )
    result = client.get_status()

    assert isinstance(result, StatusResponse)
    assert result.healthy is True
    assert result.cpu_percent == 35.5


# noinspection DuplicatedCode
@pytest.mark.anyio
async def test_a_get_status_success(httpx_mock: HTTPXMock, auth: Auth) -> None:
    """Test a_get_status returns valid StatusResponse on success."""

    httpx_mock.add_response(
        method="GET",
        url=f"{auth.base_url}/status",
        json={
            "healthy": True,
            "active_tasks": 2,
            "pending_tasks": 1,
            "max_capacity": 4,
            "cpu_count": 8,
            "cpu_percent": 35.5,
            "total_memory": 16000000000,
            "used_memory": 8000000000,
            "memory_percent": 50,
        },
        status_code=200,
    )

    client = BaseClient()
    client.configure(
        base_url=auth.base_url,  # type: ignore
        client_id=auth.client_id,  # type: ignore
        client_secret=auth.client_secret,  # type: ignore
    )
    result = await client.a_get_status()

    assert isinstance(result, StatusResponse)
    assert result.memory_percent == 50


def test_get_status_unauthorized(httpx_mock: HTTPXMock, auth: Auth) -> None:
    """Test get_status handles 401 Unauthorized error."""
    called: list[str] = []

    def on_auth_error(msg: str) -> None:
        called.append(msg)

    httpx_mock.add_response(
        method="GET",
        url=f"{auth.base_url}/status",
        json={"detail": "Unauthorized"},
        status_code=401,
    )

    client = BaseClient(on_auth_error=on_auth_error)
    client.configure(
        base_url=auth.base_url,  # type: ignore
        client_id=auth.client_id,  # type: ignore
        client_secret=auth.client_secret,  # type: ignore
    )
    client.get_status()

    assert any("Unauthorized" in msg for msg in called)


def test_get_status_request_error(httpx_mock: HTTPXMock, auth: Auth) -> None:
    """Test get_status handles network errors (RequestError)."""
    called: list[str] = []

    def on_error(msg: str) -> None:
        called.append(msg)

    httpx_mock.add_exception(httpx.RequestError("Network failure"))

    client = BaseClient(on_error=on_error)
    client.configure(
        base_url=auth.base_url,  # type: ignore
        client_id=auth.client_id,  # type: ignore
        client_secret=auth.client_secret,  # type: ignore
    )
    client.get_status()

    assert any("Network failure" in msg for msg in called)


def test_get_status_generic_exception(
    httpx_mock: HTTPXMock, auth: Auth
) -> None:
    """Test get_status handles unexpected exception gracefully."""
    called: list[str] = []

    def on_error(msg: str) -> None:
        called.append(msg)

    httpx_mock.add_exception(RuntimeError("Something exploded"))

    client = BaseClient(on_error=on_error)
    client.configure(
        base_url=auth.base_url,  # type: ignore
        client_id=auth.client_id,  # type: ignore
        client_secret=auth.client_secret,  # type: ignore
    )

    # Should not raise
    try:
        client.get_status()
    except RuntimeError:
        pytest.fail("get_status should not raise an exception")

    assert any("Something exploded" in msg for msg in called)
