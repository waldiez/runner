# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""External token verification service."""

import json
import logging
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

LOG = logging.getLogger(__name__)


class ExternalTokenResponse(BaseModel):
    """Response from external token verification."""

    valid: bool
    user_info: Dict[str, Any] = {}


async def verify_external_token(
    token: str, verify_url: str, secret: str = ""
) -> Tuple[Optional[ExternalTokenResponse], Optional[BaseException]]:
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
    Tuple[Optional[ExternalTokenResponse], Optional[BaseException]]
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
        data = response.json()
        token_response = ExternalTokenResponse(
            valid=True, user_info=data.get("user", {})
        )
        return token_response, None
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        LOG.error("Error parsing external token response: %s", exc)
        return None, HTTPException(
            status_code=500,
            detail="Error processing external verification response",
        )
