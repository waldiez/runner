# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
#
# flake8: noqa: E501
# pylint: disable=line-too-long, missing-function-docstring
# pylint: disable=missing-param-doc,missing-return-doc,protected-access
"""Test waldiez_runner.client._auth.*."""

from datetime import datetime, timedelta, timezone

import pytest
from pytest_httpx import HTTPXMock

from waldiez_runner.client._auth import CustomAuth, TokensResponse


@pytest.fixture(name="auth")
def auth_fixture() -> CustomAuth:
    """Return a new CustomAuth instance."""
    auth = CustomAuth()
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
    return {
        "access_token": "valid_access_token",  # nosemgrep # nosec
        "refresh_token": "valid_refresh_token",  # nosemgrep # nosec
        "token_type": "bearer",
        "expires_at": expires_at.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        ),
        "refresh_expires_at": refresh_expires_at.isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z"),
        "audience": "test",
    }


@pytest.fixture(name="expired_token_response")
def expired_token_response_fixture() -> TokensResponse:
    """Creates a mock expired token response."""
    now = datetime.now(timezone.utc)
    expired_at = now - timedelta(seconds=3600)
    refresh_expired_at = now - timedelta(days=30)
    return {
        "access_token": "expired_access_token",  # nosemgrep # nosec
        "refresh_token": "expired_refresh_token",  # nosemgrep # nosec
        "token_type": "bearer",
        "expires_at": expired_at.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        ),
        "refresh_expires_at": refresh_expired_at.isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z"),
        "audience": "test",
    }


def test_sync_fetch_token(
    auth: CustomAuth,
    valid_token_response: TokensResponse,
    httpx_mock: HTTPXMock,
) -> None:
    """Test fetching an access token synchronously."""
    auth._tokens_response = None

    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        json=valid_token_response,
        status_code=200,
    )

    token = auth.sync_get_token()
    assert auth.base_url == "http://localhost:8000"
    assert token == "valid_access_token"  # nosemgrep # nosec
    assert auth._tokens_response
    assert (
        auth._tokens_response["access_token"] == "valid_access_token"
    )  # nosemgrep # nosec


def test_sync_token_expired(
    auth: CustomAuth,
    expired_token_response: TokensResponse,
    valid_token_response: TokensResponse,
    httpx_mock: HTTPXMock,
) -> None:
    """Test that expired tokens are refreshed."""
    auth._tokens_response = expired_token_response
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        json=valid_token_response,
        status_code=200,
    )

    assert auth.has_valid_token() is False
    token = auth.sync_get_token()
    assert token == "valid_access_token"  # nosemgrep # nosec
    assert auth._tokens_response
    assert (
        auth._tokens_response["access_token"] == "valid_access_token"
    )  # nosemgrep # nosec


def test_sync_token_refresh_not_expired(
    auth: CustomAuth,
    valid_token_response: TokensResponse,
    httpx_mock: HTTPXMock,
) -> None:
    """Test that not expired tokens are not refreshed."""
    auth._tokens_response = valid_token_response
    auth._tokens_response["expires_at"] = (
        (datetime.now(timezone.utc) - timedelta(seconds=3600))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    auth._tokens_response["refresh_expires_at"] = (
        (datetime.now(timezone.utc) + timedelta(days=30))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token/refresh",
        json=valid_token_response,
        status_code=200,
    )

    token = auth.sync_get_token()
    assert token == "valid_access_token"  # nosemgrep # nosec
    assert auth._tokens_response
    assert (
        auth._tokens_response["access_token"] == "valid_access_token"
    )  # nosemgrep # nosec


@pytest.mark.anyio
async def test_async_fetch_token(
    auth: CustomAuth,
    valid_token_response: TokensResponse,
    httpx_mock: HTTPXMock,
) -> None:
    """Test fetching an access token asynchronously."""
    auth._tokens_response = None

    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        json=valid_token_response,
        status_code=200,
    )

    token = await auth.async_get_token()
    assert token == "valid_access_token"  # nosemgrep # nosec
    assert auth._tokens_response
    assert (
        auth._tokens_response["access_token"] == "valid_access_token"
    )  # nosemgrep # nosec


def test_sync_invalid_client(
    auth: CustomAuth,
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
    auth: CustomAuth,
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
    auth: CustomAuth,
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
    auth: CustomAuth,
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
