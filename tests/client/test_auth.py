# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.
#
# flake8: noqa: E501
# pylint: disable=line-too-long, missing-function-docstring
# pylint: disable=missing-param-doc,missing-return-doc,protected-access
# pyright: reportPrivateUsage=false,reportAttributeAccessIssue=false

"""Test waldiez_runner.client._auth.*."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from pytest import LogCaptureFixture
from pytest_httpx import HTTPXMock

from waldiez_runner.client import Auth, TokensResponse


@pytest.fixture(name="auth")
def auth_fixture() -> Auth:
    """Return a new Auth instance."""
    auth = Auth()
    auth.configure(
        "client_id", "client_secret", base_url="http://localhost:8000"
    )
    return auth


@pytest.fixture(name="valid_token_response")
def valid_token_response_fixture() -> TokensResponse:
    """Creates a mock valid token response."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=3600)
    refresh_expires_at = now + timedelta(days=30)
    return TokensResponse.model_validate(
        {
            "access_token": "valid_access_token",  # nosemgrep # nosec
            "refresh_token": "valid_refresh_token",  # nosemgrep # nosec
            "token_type": "bearer",
            "expires_at": expires_at.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "refresh_expires_at": refresh_expires_at.isoformat(
                timespec="milliseconds"
            ).replace("+00:00", "Z"),
            "audience": "tasks-api",
        }
    )


@pytest.fixture(name="expired_token_response")
def expired_token_response_fixture() -> TokensResponse:
    """Creates a mock expired token response."""
    now = datetime.now(timezone.utc)
    expired_at = now - timedelta(seconds=3600)
    refresh_expired_at = now - timedelta(days=30)
    return TokensResponse.model_validate(
        {
            "access_token": "expired_access_token",  # nosemgrep # nosec
            "refresh_token": "expired_refresh_token",  # nosemgrep # nosec
            "token_type": "bearer",
            "expires_at": expired_at.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "refresh_expires_at": refresh_expired_at.isoformat(
                timespec="milliseconds"
            ).replace("+00:00", "Z"),
            "audience": "tasks-api",
        }
    )


def test_sync_fetch_token(
    auth: Auth,
    valid_token_response: TokensResponse,
    httpx_mock: HTTPXMock,
) -> None:
    """Test fetching an access token synchronously."""
    auth._tokens_response = None

    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        json=valid_token_response.model_dump(),
        status_code=200,
    )

    token = auth.sync_get_token()
    assert auth.base_url == "http://localhost:8000"
    assert token == "valid_access_token"  # nosemgrep # nosec
    assert auth._tokens_response
    assert (
        auth._tokens_response.access_token
        == "valid_access_token"  # nosemgrep # nosec
    )


def test_sync_token_expired(
    auth: Auth,
    expired_token_response: TokensResponse,
    valid_token_response: TokensResponse,
    httpx_mock: HTTPXMock,
) -> None:
    """Test that expired tokens are refreshed."""
    auth._tokens_response = expired_token_response
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        json=valid_token_response.model_dump(),
        status_code=200,
    )

    assert auth.has_valid_token() is False
    token = auth.sync_get_token()
    assert token == "valid_access_token"  # nosemgrep # nosec
    assert auth._tokens_response
    assert (
        auth._tokens_response.access_token
        == "valid_access_token"  # nosemgrep # nosec
    )


def test_sync_token_refresh_not_expired(
    auth: Auth,
    valid_token_response: TokensResponse,
    httpx_mock: HTTPXMock,
) -> None:
    """Test that not expired tokens are not refreshed."""
    auth._tokens_response = valid_token_response
    auth._tokens_response.expires_at = (
        (datetime.now(timezone.utc) - timedelta(seconds=3600))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    auth._tokens_response.refresh_expires_at = (
        (datetime.now(timezone.utc) + timedelta(days=30))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token/refresh",
        json=valid_token_response.model_dump(),
        status_code=200,
    )

    token = auth.sync_get_token()
    assert token == "valid_access_token"  # nosemgrep # nosec
    assert auth._tokens_response
    assert (
        auth._tokens_response.access_token
        == "valid_access_token"  # nosemgrep # nosec
    )


@pytest.mark.anyio
async def test_async_fetch_token(
    auth: Auth,
    valid_token_response: TokensResponse,
    httpx_mock: HTTPXMock,
) -> None:
    """Test fetching an access token asynchronously."""
    auth._tokens_response = None

    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        json=valid_token_response.model_dump(),
        status_code=200,
    )

    token = await auth.async_get_token()
    assert token == "valid_access_token"  # nosemgrep # nosec
    assert auth._tokens_response
    assert (
        auth._tokens_response.access_token
        == "valid_access_token"  # nosemgrep # nosec
    )


def test_sync_invalid_client(
    auth: Auth,
    httpx_mock: HTTPXMock,
) -> None:
    """Test handling of invalid client credentials (sync)."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        status_code=401,
        text="Invalid client credentials",
    )

    auth.configure("invalid_client_id", "invalid_client_secret")

    def on_error(message: str) -> None:
        """Check the error message."""
        assert "Invalid client credentials" in message

    auth.on_error = on_error
    auth.sync_get_token()


def test_sync_http_error(
    auth: Auth,
    httpx_mock: HTTPXMock,
) -> None:
    """Test handling of HTTP errors when fetching tokens."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        status_code=500,
        text="Internal Server Error",
    )

    auth.configure("client_id", "client_secret")

    def on_error(message: str) -> None:
        """Check the error message."""
        assert "Internal Server Error" in message

    auth.on_error = on_error
    auth.sync_get_token()


@pytest.mark.anyio
async def test_async_invalid_client(
    auth: Auth,
    httpx_mock: HTTPXMock,
) -> None:
    """Test handling of invalid client credentials (async)."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        status_code=401,
        text="Invalid client credentials",
    )

    auth.configure("invalid_client_id", "invalid_client_secret")

    async def on_error(message: str) -> None:
        """Check the error message."""
        assert "Invalid client credentials" in message

    auth.on_error = on_error
    await auth.async_get_token()


@pytest.mark.anyio
async def test_async_http_error(
    auth: Auth,
    httpx_mock: HTTPXMock,
) -> None:
    """Test handling of HTTP errors when fetching tokens asynchronously."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        status_code=500,
        text="Internal Server Error",
    )

    auth.configure("client_id", "client_secret")

    async def on_error(message: str) -> None:
        """Check the error message."""
        assert "Internal Server Error" in message

    auth.on_error = on_error
    await auth.async_get_token()


def test_force_sync_fetch_token(
    auth: Auth,
    valid_token_response: TokensResponse,
    httpx_mock: HTTPXMock,
) -> None:
    """Force a token fetch even if a valid one exists."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        json=valid_token_response.model_dump(),
        status_code=200,
    )
    token = auth.sync_get_token(force=True)
    assert token == "valid_access_token"  # nosemgrep # nosec


@pytest.mark.anyio
async def test_force_async_fetch_token(
    auth: Auth,
    valid_token_response: TokensResponse,
    httpx_mock: HTTPXMock,
) -> None:
    """Force an async token fetch."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        json=valid_token_response.model_dump(),
        status_code=200,
    )
    token = await auth.async_get_token(force=True)
    assert token == "valid_access_token"  # nosemgrep # nosec


def test_is_expired_invalid_datetime(auth: Auth) -> None:
    """Test _is_expired with invalid datetime format."""
    auth._tokens_response = TokensResponse.model_validate(
        {
            "expires_at": "not-a-datetime",
            "refresh_expires_at": "still-not-a-date",
            "access_token": "abc",
            "refresh_token": "def",
            "token_type": "bearer",
            "audience": "tasks-api",
        }
    )
    assert auth.is_token_expired()
    assert auth.is_refresh_token_expired()


def test_handle_token_sync(auth: Auth) -> None:
    """Test _handle_token with sync callback."""
    called: list[str] = []

    def token_callback(t: str) -> None:
        called.append(t)

    auth.on_token = token_callback
    auth._handle_token("abc123")
    assert called == ["abc123"]


@pytest.mark.anyio
async def test_handle_token_async(auth: Auth) -> None:
    """Test _handle_token with async callback."""

    result = {}

    async def token_callback(t: str) -> None:
        result["value"] = t

    auth.on_token = token_callback
    auth._handle_token("def456")
    await asyncio.sleep(0.05)  # Let the callback task complete
    assert result["value"] == "def456"


def test_fetch_token_missing_client(
    auth: Auth,
    caplog: LogCaptureFixture,
) -> None:
    """Missing client ID and secret leads to error."""
    auth._client_id = None
    auth._client_secret = None
    auth._fetch_token()
    assert "Client ID and secret are not configured" in caplog.text


def test_fetch_token_missing_endpoint(
    auth: Auth,
    caplog: LogCaptureFixture,
) -> None:
    """Missing token endpoint triggers error."""
    auth._client_id = "id"
    auth._client_secret = "secret"  # nosemgrep # nosec
    auth._base_url = None
    auth._fetch_token()
    assert "Token endpoint is not configured" in caplog.text


@pytest.mark.anyio
async def test_async_fetch_token_missing_client(auth: Auth) -> None:
    auth._client_id = None
    auth._client_secret = None
    await auth._async_fetch_token()  # Should not raise


@pytest.mark.anyio
async def test_async_refresh_token_missing(auth: Auth) -> None:
    auth._tokens_response = {}  # type: ignore[assignment]
    await auth._async_refresh_access_token()  # Should not raise


def test_sync_refresh_token_missing(auth: Auth) -> None:
    auth._tokens_response = {}  # type: ignore[assignment]
    auth._refresh_access_token()  # Should not raise


@pytest.mark.anyio
async def test_async_refresh_access_token_success(
    auth: Auth,
    valid_token_response: TokensResponse,
    httpx_mock: HTTPXMock,
) -> None:
    """Test refreshing access token asynchronously (200 OK)."""
    auth._tokens_response = valid_token_response

    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token/refresh",
        json=valid_token_response.model_dump(),
        status_code=200,
    )

    await auth._async_refresh_access_token()
    assert auth._tokens_response is not None
    assert (
        auth._tokens_response.access_token
        == "valid_access_token"  # nosemgrep # nosec
    )
