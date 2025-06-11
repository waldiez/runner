# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-param-doc,too-few-public-methods
# pylint: disable=missing-yield-doc,disable=line-too-long, unused-argument
"""Test waldiez_runner.routes.ws.auth.*."""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket

from waldiez_runner.config import Settings
from waldiez_runner.routes.ws.auth import (
    _get_jwt_from_auth_header,
    _get_jwt_from_cookie,
    _get_jwt_from_subprotocol,
    get_ws_client_id,
)
from waldiez_runner.services.external_token_service import ExternalTokenService

MODULE_TO_PATCH = "waldiez_runner.routes.ws.auth"


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


@pytest.mark.asyncio
async def test_get_ws_client_id_with_external_auth_success() -> None:
    """Test get_ws_client_id with successful external auth."""
    settings = MagicMock(spec=Settings)
    settings.enable_external_auth = True

    websocket = MagicMock(spec=WebSocket)
    websocket.headers = {"Authorization": "Bearer external-token"}
    websocket.query_params = {}
    websocket.cookies = {}
    websocket.state = MagicMock()

    mock_get_client_id = AsyncMock(return_value=(None, "some error"))

    mock_token_response = ExternalTokenService.ExternalTokenResponse(
        valid=True, user_info={"id": "user123", "name": "Test User"}
    )
    mock_verify_external = AsyncMock(return_value=(mock_token_response, None))

    with (
        patch(
            f"{MODULE_TO_PATCH}.get_client_id_from_token", mock_get_client_id
        ),
        patch(
            f"{MODULE_TO_PATCH}.verify_external_auth_token",
            mock_verify_external,
        ),
    ):
        client_id, subprotocol = await get_ws_client_id(websocket, settings)

    assert client_id == "external"
    assert subprotocol is None
    assert websocket.state.external_user_info == {
        "id": "user123",
        "name": "Test User",
    }
    mock_get_client_id.assert_called_once()
    mock_verify_external.assert_called_once_with("external-token", settings)


@pytest.mark.asyncio
async def test_get_ws_client_id_with_external_auth_disabled() -> None:
    """Test get_ws_client_id with external auth disabled."""
    settings = MagicMock(spec=Settings)
    settings.enable_external_auth = False

    websocket = MagicMock(spec=WebSocket)
    websocket.headers = {"Authorization": "Bearer external-token"}
    websocket.query_params = {}
    websocket.cookies = {}
    websocket.state = MagicMock()

    mock_get_client_id = AsyncMock(return_value=(None, "some error"))

    mock_verify_external = AsyncMock()

    with (
        patch(
            f"{MODULE_TO_PATCH}.get_client_id_from_token", mock_get_client_id
        ),
        patch(
            f"{MODULE_TO_PATCH}.verify_external_auth_token",
            mock_verify_external,
        ),
    ):
        client_id, subprotocol = await get_ws_client_id(websocket, settings)

    assert client_id is None
    assert subprotocol is None
    mock_get_client_id.assert_called_once()
    mock_verify_external.assert_not_called()


@pytest.mark.asyncio
async def test_get_ws_client_id_with_external_auth_failure() -> None:
    """Test get_ws_client_id with external auth failure."""
    settings = MagicMock(spec=Settings)
    settings.enable_external_auth = True

    websocket = MagicMock(spec=WebSocket)
    websocket.headers = {"Authorization": "Bearer external-token"}
    websocket.query_params = {}
    websocket.cookies = {}
    websocket.state = MagicMock()

    mock_get_client_id = AsyncMock(return_value=(None, "some error"))

    mock_token_response = ExternalTokenService.ExternalTokenResponse(
        valid=False, user_info={}
    )
    mock_verify_external = AsyncMock(
        return_value=(mock_token_response, "external validation error")
    )

    with (
        patch(
            f"{MODULE_TO_PATCH}.get_client_id_from_token", mock_get_client_id
        ),
        patch(
            f"{MODULE_TO_PATCH}.verify_external_auth_token",
            mock_verify_external,
        ),
    ):
        client_id, subprotocol = await get_ws_client_id(websocket, settings)

    assert client_id is None
    assert subprotocol is None
    mock_get_client_id.assert_called_once()
    mock_verify_external.assert_called_once()


@pytest.mark.asyncio
async def test_get_ws_client_id_external_auth_exception() -> None:
    """Test get_ws_client_id handling external auth exceptions."""
    settings = MagicMock(spec=Settings)
    settings.enable_external_auth = True

    websocket = MagicMock(spec=WebSocket)
    websocket.headers = {"Authorization": "Bearer external-token"}
    websocket.query_params = {}
    websocket.cookies = {}
    websocket.state = MagicMock()

    mock_get_client_id = AsyncMock(return_value=(None, "some error"))

    mock_verify_external = AsyncMock(
        side_effect=Exception("External auth service unavailable")
    )

    with (
        patch(
            f"{MODULE_TO_PATCH}.get_client_id_from_token", mock_get_client_id
        ),
        patch(
            f"{MODULE_TO_PATCH}.verify_external_auth_token",
            mock_verify_external,
        ),
        patch(f"{MODULE_TO_PATCH}.LOG") as mock_log,
    ):
        client_id, subprotocol = await get_ws_client_id(websocket, settings)

    assert client_id is None
    assert subprotocol is None
    mock_get_client_id.assert_called_once()
    mock_verify_external.assert_called_once()
    mock_log.warning.assert_any_call(
        "External validation error for auth header token: "
        "External auth service unavailable"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token_source,expected_subprotocol",
    [
        ("query_params", None),
        ("cookie", None),
        ("auth_header", None),
        ("subprotocol", "tasks-api"),
    ],
)
async def test_get_ws_client_id_external_auth_from_different_sources(
    token_source: str, expected_subprotocol: str | None
) -> None:
    """Test get_ws_client_id with external auth from different sources."""
    settings = MagicMock(spec=Settings)
    settings.enable_external_auth = True

    websocket = MagicMock(spec=WebSocket)
    websocket.headers = {}
    websocket.query_params = {}
    websocket.cookies = {}
    websocket.state = MagicMock()

    if token_source == "query_params":  # nosec B105
        websocket.query_params = {"access_token": "external-token"}
    elif token_source == "cookie":  # nosec B105
        websocket.cookies = {"access_token": "external-token"}
    elif token_source == "auth_header":  # nosec B105
        websocket.headers = {"Authorization": "Bearer external-token"}
    elif token_source == "subprotocol":  # nosec B105
        websocket.headers = {
            "Sec-WebSocket-Protocol": "tasks-api, external-token"
        }

    mock_get_client_id = AsyncMock(return_value=(None, "some error"))

    mock_token_response = ExternalTokenService.ExternalTokenResponse(
        valid=True, user_info={"id": "user123"}
    )
    mock_verify_external = AsyncMock(return_value=(mock_token_response, None))

    with (
        patch(
            f"{MODULE_TO_PATCH}.get_client_id_from_token", mock_get_client_id
        ),
        patch(
            f"{MODULE_TO_PATCH}.verify_external_auth_token",
            mock_verify_external,
        ),
    ):
        client_id, subprotocol = await get_ws_client_id(websocket, settings)

    assert client_id == "external"
    assert subprotocol == expected_subprotocol
    assert websocket.state.external_user_info == {"id": "user123"}
