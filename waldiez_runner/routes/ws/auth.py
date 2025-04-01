# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Websocket authentication.

Way to get the client ID from the WebSocket connection:
- Auth header ({Authorization: Bearer <token>})
- Subprotocol (task-api, <token>)
- Cookie (access_token)
- Query parameter (?access_token=<token>)
Recommended: Auth header if Python client, subprotocol if JS client.
"""

import logging
from typing import Tuple

from fastapi import Depends, WebSocket

from waldiez_runner.config import Settings
from waldiez_runner.dependencies import (
    TASK_API_AUDIENCE,
    JWKSCache,
    get_client_id_from_token,
    get_jwks_cache,
    get_settings,
)

LOG = logging.getLogger(__name__)


async def get_ws_client_id(
    websocket: WebSocket,
    settings: Settings = Depends(get_settings),
    jwks_cache: JWKSCache = Depends(get_jwks_cache),
) -> Tuple[str | None, str | None]:
    """Get the client ID from the WebSocket connection.

    Parameters
    ----------
    websocket: WebSocket
        The WebSocket connection.
    settings: Settings
        The app settings.
    jwks_cache: JWKSCache
        The JWKS cache.

    Returns
    -------
    Tuple[str | None, str | None]
        The client ID and the subprotocol to use to accept the connection.
    """
    query_token = _get_jwt_from_query_params(websocket)
    if query_token:
        client_id, _ = await get_client_id_from_token(
            expected_audience=TASK_API_AUDIENCE,
            token=query_token,
            settings=settings,
            jwks_cache=jwks_cache,
        )
        return client_id, None
    jwt_cookie = _get_jwt_from_cookie(websocket)
    if jwt_cookie:
        LOG.debug("Found token in cookie")
        client_id, _ = await get_client_id_from_token(
            expected_audience=TASK_API_AUDIENCE,
            token=jwt_cookie,
            settings=settings,
            jwks_cache=jwks_cache,
        )
        return client_id, None
    jwt_auth_header = _get_jwt_from_auth_header(websocket)
    if jwt_auth_header:
        LOG.debug("Found token in auth header")
        client_id, _ = await get_client_id_from_token(
            expected_audience=TASK_API_AUDIENCE,
            token=jwt_auth_header,
            settings=settings,
            jwks_cache=jwks_cache,
        )
        return client_id, None
    jwt_from_subprotocol = _get_jwt_from_subprotocol(websocket)
    if jwt_from_subprotocol:
        LOG.debug("Found token in subprotocol")
        client_id, _ = await get_client_id_from_token(
            expected_audience=TASK_API_AUDIENCE,
            token=jwt_from_subprotocol,
            settings=settings,
            jwks_cache=jwks_cache,
        )
        return client_id, TASK_API_AUDIENCE
    return None, None


def _get_jwt_from_cookie(websocket: WebSocket) -> str | None:
    """Get the jwt from the WebSocket connection cookie."""
    return websocket.cookies.get("access_token", None)


def _get_jwt_from_query_params(websocket: WebSocket) -> str | None:
    """Get the jwt from the WebSocket connection query parameters."""
    return websocket.query_params.get("access_token", None)


def _get_jwt_from_auth_header(websocket: WebSocket) -> str | None:
    """Get the client ID from the WebSocket connection authorization header."""
    auth_header = websocket.headers.get("Authorization", None)
    if not auth_header:
        return None
    header_parts = auth_header.split()
    if len(header_parts) != 2:
        return None
    if header_parts[0].lower() != "bearer":
        return None
    return header_parts[1]


def _get_jwt_from_subprotocol(
    websocket: WebSocket,
) -> str | None:
    """Get the client ID from the WebSocket connection subprotocol."""
    sec_protocol = websocket.headers.get("Sec-WebSocket-Protocol", None)
    if not sec_protocol:
        LOG.warning("No sub protocol")
        return None
    sec_parts = sec_protocol.split(",")
    if len(sec_parts) != 2:
        LOG.warning("Invalid sub protocol")
        return None
    if sec_parts[0].lower() != TASK_API_AUDIENCE:
        LOG.warning("Invalid sub protocol content")
        return None
    return sec_parts[1].strip()
