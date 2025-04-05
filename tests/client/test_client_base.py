# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pylint: disable=missing-param-doc,missing-return-doc
# pylint: disable=protected-access,unused-argument
"""Test waldiez_runner.client._client_base.*."""

import asyncio
from typing import Any, Coroutine, List
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from waldiez_runner.client.client_base import BaseClient


@pytest.fixture(name="base_client")
def base_client_fixture() -> BaseClient:
    """Return a new BaseClient instance."""
    return BaseClient()


def test_configure_sets_auth_and_handlers() -> None:
    """Test that configure sets the auth and handlers correctly."""

    def token_cb(token: str) -> None:
        """Token callback."""

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


def test_authenticate_success(mocker: MockerFixture) -> None:
    """Test that authenticate returns True when auth is successful."""
    client = BaseClient()
    client.auth = MagicMock()
    client.auth.base_url = "url"
    client.auth.client_id = "id"
    client.auth.client_secret = "secret"  # nosemgrep # nosec
    client.auth.sync_get_token = MagicMock()
    assert client.authenticate()


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
    called: List[str] = []

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
    called: List[str] = []

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


def test_handle_auth_error_async_fallback_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that handle_auth_error calls the callback."""
    called: List[str] = []

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
    called: List[str] = []

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
    called: List[str] = []

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


def test_handle_error_async_fallback_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that handle_error calls the callback."""
    called: List[str] = []

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


# Dummy loop for async task scheduling
# pylint: disable=too-few-public-methods,no-self-use
class DummyLoop:
    """Dummy loop for async task scheduling."""

    def create_task(self, coro: Coroutine[Any, Any, None]) -> None:
        """Create a task."""
        asyncio.get_event_loop().run_until_complete(coro)
