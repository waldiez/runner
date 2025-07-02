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
from typing import Any, Tuple, cast

from fastapi import Depends, WebSocket

from waldiez_runner.config import Settings
from waldiez_runner.dependencies import (
    TASK_API_AUDIENCE,
    JWKSCache,
    get_client_id_from_token,
    get_jwks_cache,
    get_settings,
)
from waldiez_runner.dependencies.auth import verify_external_auth_token

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
    token_sources: list[dict[str, Any]] = [
        {
            "method": _get_jwt_from_query_params,
            "name": "query parameters",
            "subprotocol": None,
        },
        {"method": _get_jwt_from_cookie, "name": "cookie", "subprotocol": None},
        {
            "method": _get_jwt_from_auth_header,
            "name": "auth header",
            "subprotocol": None,
        },
        {
            "method": _get_jwt_from_subprotocol,
            "name": "subprotocol",
            "subprotocol": TASK_API_AUDIENCE,
        },
    ]

    # Try each token source in order of priority
    for source in token_sources:
        token = source["method"](websocket)  # pyright: ignore
        if not token:
            continue

        LOG.debug("Found token in %s", source["name"])

        # Try internal validation
        client_id, exception = await get_client_id_from_token(
            expected_audience=TASK_API_AUDIENCE,
            token=token,
            settings=settings,
            jwks_cache=jwks_cache,
        )

        if client_id and not exception:
            subprotocol = cast(str | None, source["subprotocol"])
            return client_id, subprotocol

        # Try external validation if enabled and internal failed
        if settings.enable_external_auth:
            try:
                external_validated = await _try_external_validation(
                    token, settings, websocket
                )
            except (ValueError, ConnectionError, TimeoutError) as err:
                LOG.warning(
                    "External validation error for %s token: %s",
                    source["name"],
                    err,
                )
                external_validated = False

            if external_validated:
                subprotocol = cast(str | None, source["subprotocol"])
                return "external", subprotocol

    # No valid token found
    return None, None


async def _try_external_validation(
    token: str, settings: Settings, websocket: WebSocket
) -> bool:
    """Try to validate token with external service.

    Parameters
    ----------
    token : str
        The token to validate
    settings : Settings
        Application settings
    websocket : WebSocket
        The websocket connection

    Returns
    -------
    bool
        True if validation succeeded, False otherwise
    """
    token_response, ext_exception = await verify_external_auth_token(
        token, settings
    )

    if token_response and not ext_exception and token_response.valid:
        # Store user info on websocket state
        websocket.state.external_user_info = token_response.user_info
        return True
    return False


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
