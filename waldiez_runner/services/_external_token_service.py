# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pyright: reportUnreachable=false,reportUnnecessaryIsInstance=false

"""External token verification service."""

import json
import logging
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

LOG = logging.getLogger(__name__)


class ExternalTokenResponse(BaseModel):
    """Response from external token verification."""

    valid: bool
    id: str
    user_info: dict[str, Any] = {}


async def verify_external_token(
    token: str, verify_url: str, secret: str = ""
) -> tuple[ExternalTokenResponse | None, BaseException | None]:
    """Verify an external token by sending it to a verification endpoint.

    Parameters
    ----------
    token : str
        The token to verify
    verify_url : str
        The URL to send the verification request to
    secret : str, optional
        Secret to include in the verification request, by default ""

    Returns
    -------
    tuple[Optional[ExternalTokenResponse], Optional[BaseException]]
        A tuple containing the verification response (if successful) and an
        exception (if verification failed)
    """
    payload = {"token": token}
    if secret:
        payload["secret"] = secret

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(verify_url, json=payload, timeout=10.0)
    except httpx.RequestError as exc:
        LOG.error("Error verifying external token: %s", exc)
        return None, HTTPException(
            status_code=500, detail="External verification service unavailable"
        )

    if response.status_code != 200:
        LOG.warning(
            "External token verification failed: %s %s",
            response.status_code,
            response.text,
        )
        return None, HTTPException(
            status_code=401, detail="External token verification failed"
        )

    try:
        user_info, client_id = get_user_info(response, token)
        token_response = ExternalTokenResponse(
            valid=True,
            id=client_id,
            user_info=user_info,
        )
        return token_response, None
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        LOG.error("Error parsing external token response: %s", exc)
        return None, HTTPException(
            status_code=500,
            detail="Error processing external verification response",
        )


def get_user_info(
    response: httpx.Response, token: str
) -> tuple[dict[str, Any], str]:
    """Extract user information from the external token verification response.

    Parameters
    ----------
    response : httpx.Response
        The response from the external token verification request.
    token : str
        The original token that was verified.

    Returns
    -------
    dict[str, Any]
        The user information extracted from the response.
    """
    data = response.json()
    user_info: dict[str, Any] = data.get("user", data)
    if not isinstance(user_info, dict):  # pragma: no cover
        user_info = {}
    sub = user_info.get("sub", user_info.get("id", token))
    if not isinstance(sub, str):
        sub = token
    user_info["sub"] = sub
    return user_info, sub
