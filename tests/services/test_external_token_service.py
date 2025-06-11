# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Test the external token verification service."""

import pytest
from fastapi import HTTPException
from httpx import RequestError
from pytest_httpx import HTTPXMock

from waldiez_runner.services.external_token_service import ExternalTokenService


@pytest.mark.asyncio
async def test_verify_external_token_success(httpx_mock: HTTPXMock) -> None:
    """Test successful external token verification."""
    # Mock a successful response from the external verification service
    httpx_mock.add_response(
        url="https://example.com/verify",
        method="POST",
        json={
            "valid": True,
            "user": {"id": "ext-123", "name": "External User"}
        },
        status_code=200
    )
    
    response, exception = await ExternalTokenService.verify_external_token(
        "test-token", 
        "https://example.com/verify"
    )
    
    assert exception is None
    assert response is not None
    assert response.valid is True
    assert response.user_info["id"] == "ext-123"
    assert response.user_info["name"] == "External User"


@pytest.mark.asyncio
async def test_verify_external_token_invalid_response(httpx_mock: HTTPXMock) -> None:
    """Test external token verification with invalid response."""
    # Mock an unsuccessful response (401 Unauthorized)
    httpx_mock.add_response(
        url="https://example.com/verify",
        method="POST",
        json={"error": "Invalid token"},
        status_code=401
    )
    
    response, exception = await ExternalTokenService.verify_external_token(
        "invalid-token", 
        "https://example.com/verify"
    )
    
    assert response is None
    assert exception is not None
    assert isinstance(exception, HTTPException)
    assert exception.status_code == 401


@pytest.mark.asyncio
async def test_verify_external_token_service_unavailable(httpx_mock: HTTPXMock) -> None:
    """Test external token verification when service is unavailable."""
    # Mock a connection error
    httpx_mock.add_exception(
        url="https://example.com/verify",
        exception=RequestError("Connection error")
    )
    
    response, exception = await ExternalTokenService.verify_external_token(
        "test-token", 
        "https://example.com/verify"
    )
    
    assert response is None
    assert exception is not None
    assert isinstance(exception, HTTPException)
    assert exception.status_code == 500
    assert "External verification service unavailable" in str(exception.detail)