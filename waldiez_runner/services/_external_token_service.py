# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""External token verification service."""

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
    token: str, 
    verify_url: str,
    secret: str = ""
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
        A tuple containing the verification response (if successful) and an exception (if verification failed)
    """
    try:
        payload = {"token": token}
        if secret:
            payload["secret"] = secret
            
        async with httpx.AsyncClient() as client:
            response = await client.post(
                verify_url,
                json=payload,
                timeout=10.0
            )
            
        if response.status_code != 200:
            LOG.warning(f"External token verification failed: {response.status_code} {response.text}")
            return None, HTTPException(
                status_code=401, 
                detail="External token verification failed"
            )
            
        # Parse the response from the external verifier
        data = response.json()
        token_response = ExternalTokenResponse(
            valid=True,
            user_info=data.get("user", {})
        )
        
        return token_response, None
            
    except httpx.RequestError as exc:
        LOG.error(f"Error verifying external token: {exc}")
        return None, HTTPException(
            status_code=500,
            detail=f"External verification service unavailable"
        )