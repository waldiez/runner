# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-param-doc,too-few-public-methods
# pylint: disable=missing-yield-doc,disable=line-too-long, unused-argument
"""Test waldiez_runner.routes.ws.auth.*."""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from waldiez_runner.routes.ws.auth import (
    _get_jwt_from_auth_header,
    _get_jwt_from_cookie,
    _get_jwt_from_subprotocol,
    get_ws_client_id,
)


class MockWebSocket:
    """Fake WebSocket object with modifiable headers and cookies."""

    def __init__(
        self,
        headers: Dict[str, Any] | None = None,
        cookies: Dict[str, Any] | None = None,
        query_params: Dict[str, Any] | None = None,
    ) -> None:
        """Initialize the fake WebSocket object."""
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.query_params = query_params or {}


@pytest.mark.anyio
@patch(
    "waldiez_runner.routes.ws.auth.get_client_id_from_token",
    new_callable=AsyncMock,
)
async def test_get_ws_client_id_with_query_token(
    mock_get_client_id_from_token: AsyncMock,
) -> None:
    """Test WebSocket authentication via query token."""
    mock_get_client_id_from_token.return_value = ("test-client-id", None)
    websocket = MockWebSocket(query_params={"access_token": "mock-query-token"})
    client_id, subprotocol = await get_ws_client_id(
        websocket,  # type: ignore
        settings=MagicMock(),
        jwks_cache=MagicMock(),
    )
    assert client_id == "test-client-id"
    assert subprotocol is None
    mock_get_client_id_from_token.assert_awaited_once()


@pytest.mark.anyio
@patch(
    "waldiez_runner.routes.ws.auth.get_client_id_from_token",
    new_callable=AsyncMock,
)
async def test_get_ws_client_id_with_cookie(
    mock_get_client_id_from_token: AsyncMock,
) -> None:
    """Test WebSocket authentication via cookie token."""
    websocket = MockWebSocket(cookies={"access_token": "mock-cookie-token"})
    mock_get_client_id_from_token.return_value = ("test-client-id", None)
    client_id, subprotocol = await get_ws_client_id(
        websocket,  # type: ignore
        settings=MagicMock(),
        jwks_cache=MagicMock(),
    )
    assert client_id == "test-client-id"
    assert subprotocol is None
    mock_get_client_id_from_token.assert_awaited_once()


@pytest.mark.anyio
@patch(
    "waldiez_runner.routes.ws.auth.get_client_id_from_token",
    new_callable=AsyncMock,
)
async def test_get_ws_client_id_with_auth_header(
    mock_get_client_id_from_token: AsyncMock,
) -> None:
    """Test WebSocket authentication via Authorization header."""
    mock_get_client_id_from_token.return_value = ("test-client-id", None)
    websocket = MockWebSocket(
        headers={
            "Authorization": "Bearer mock-header-token"  # nosemgrep # nosec
        }
    )
    client_id, subprotocol = await get_ws_client_id(
        websocket,  # type: ignore
        settings=MagicMock(),
        jwks_cache=MagicMock(),
    )
    assert client_id == "test-client-id"
    assert subprotocol is None
    mock_get_client_id_from_token.assert_awaited_once()


@pytest.mark.anyio
@patch(
    "waldiez_runner.routes.ws.auth.get_client_id_from_token",
    new_callable=AsyncMock,
)
async def test_get_ws_client_id_with_subprotocol(
    mock_get_client_id_from_token: AsyncMock,
) -> None:
    """Test WebSocket authentication via subprotocol."""
    mock_get_client_id_from_token.return_value = ("test-client-id", None)
    websocket = MockWebSocket(
        headers={
            "Sec-WebSocket-Protocol": "tasks-api,mock-token"  # nosemgrep # nosec  # noqa: E501
        }
    )
    client_id, subprotocol = await get_ws_client_id(
        websocket,  # type: ignore
        settings=MagicMock(),
        jwks_cache=MagicMock(),
    )
    assert client_id == "test-client-id"
    assert subprotocol == "tasks-api"
    mock_get_client_id_from_token.assert_awaited_once()


@pytest.mark.anyio
@patch(
    "waldiez_runner.routes.ws.auth.get_client_id_from_token",
    new_callable=AsyncMock,
)
async def test_get_ws_client_id_no_auth(
    mock_get_client_id_from_token: AsyncMock,
) -> None:
    """Test WebSocket authentication with no valid authentication method."""
    mock_get_client_id_from_token.return_value = (None, None)
    websocket = MockWebSocket()
    client_id, subprotocol = await get_ws_client_id(
        websocket,  # type: ignore
        settings=MagicMock(),
        jwks_cache=MagicMock(),
    )
    assert client_id is None
    assert subprotocol is None
    mock_get_client_id_from_token.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "cookies, expected_token",
    [
        ({"access_token": "cookie-token"}, "cookie-token"),
        ({}, None),
    ],
)
async def test_get_jwt_from_cookie(
    cookies: Dict[str, str],
    expected_token: str | None,
) -> None:
    """Test JWT extraction from cookies."""
    websocket = MockWebSocket(cookies=cookies)
    token = _get_jwt_from_cookie(websocket)  # type: ignore
    assert token == expected_token


@pytest.mark.anyio
@pytest.mark.parametrize(
    "headers, expected_token",
    [
        ({"Authorization": "Bearer header-token"}, "header-token"),
        ({"Authorization": "InvalidFormat"}, None),
        ({"Authorization": "Invalid Format"}, None),
        ({}, None),
    ],
)
def test_get_jwt_from_auth_header(
    headers: Dict[str, str],
    expected_token: str | None,
) -> None:
    """Test JWT extraction from Authorization header."""
    websocket = MockWebSocket(headers=headers)
    token = _get_jwt_from_auth_header(websocket)  # type: ignore
    assert token == expected_token


@pytest.mark.anyio
@pytest.mark.parametrize(
    "headers, expected_token",
    [
        ({"Sec-WebSocket-Protocol": "some-protocol"}, None),
        ({"Sec-WebSocket-Protocol": "Invalid,Format"}, None),
        ({}, None),
        ({"Sec-WebSocket-Protocol": "tasks-api,a-token"}, "a-token"),
    ],
)
def test_get_jwt_from_subprotocol(
    headers: Dict[str, str],
    expected_token: str | None,
) -> None:
    """Test JWT extraction from WebSocket subprotocol."""
    websocket = MockWebSocket(headers=headers)
    token = _get_jwt_from_subprotocol(websocket)  # type: ignore
    assert token == expected_token
