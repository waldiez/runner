# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pyright: reportPrivateUsage=false
"""Test task permission checking functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import HTTPStatusError

from waldiez_runner.dependencies.context import RequestContext
from waldiez_runner.routes.v1.task_permission import check_user_can_run_task

TASK_PERMISSION = "waldiez_runner.routes.v1.task_permission"
APP_STATE = f"{TASK_PERMISSION}.app_state"
HTTPX_ASYNC_CLIENT = f"{TASK_PERMISSION}.httpx.AsyncClient"


@pytest.mark.asyncio
@patch(APP_STATE)
async def test_check_user_can_run_task_external_auth_disabled(
    mock_app_state: AsyncMock,
) -> None:
    """Test permission check when external auth is disabled.

    Parameters
    ----------
    mock_app_state : AsyncMock
        Mock for the app_state fixture.
    """

    # Mock settings with external auth disabled
    mock_settings = AsyncMock()
    mock_settings.enable_external_auth = False
    mock_app_state.settings = mock_settings

    context = RequestContext()

    # Should not raise any exception
    await check_user_can_run_task(context)


@pytest.mark.asyncio
@patch(APP_STATE)
async def test_check_user_can_run_task_missing_settings(
    mock_app_state: AsyncMock,
) -> None:
    """Test permission check when settings are not initialized.

    Parameters
    ----------
    mock_app_state : AsyncMock
        Mock for the app_state fixture.
    """

    # Mock settings as None
    mock_app_state.settings = None

    context = RequestContext()

    # Should raise HTTPException with 500 status
    with pytest.raises(HTTPException) as exc_info:
        await check_user_can_run_task(context)

    assert exc_info.value.status_code == 500
    assert "Settings not initialized" in exc_info.value.detail


@pytest.mark.asyncio
@patch(APP_STATE)
async def test_check_user_can_run_task_missing_config(
    mock_app_state: AsyncMock,
) -> None:
    """Test permission check when verify URL or secret is not configured.

    Parameters
    ----------
    mock_app_state : AsyncMock
        Mock for the app_state fixture.
    """

    # Mock settings with external auth enabled but missing config
    mock_settings = AsyncMock()
    mock_settings.enable_external_auth = True
    mock_settings.task_permission_verify_url = ""
    mock_settings.task_permission_secret = ""  # nosec
    mock_app_state.settings = mock_settings

    context = RequestContext()
    context.external_user_info = {"sub": "user123"}

    # Should not raise any exception (warning logged but check skipped)
    await check_user_can_run_task(context)


@pytest.mark.asyncio
@patch(APP_STATE)
async def test_check_user_can_run_task_missing_user_info(
    mock_app_state: AsyncMock,
) -> None:
    """Test permission check when user info is missing.

    Parameters
    ----------
    mock_app_state : AsyncMock
        Mock for the app_state fixture.
    """

    # Mock settings
    mock_settings = AsyncMock()
    mock_settings.enable_external_auth = True
    mock_settings.task_permission_verify_url = "https://api.example.com/check"
    mock_settings.task_permission_secret = "test-secret"  # nosec
    mock_app_state.settings = mock_settings

    # Create context without user info
    context = RequestContext()
    context.external_user_info = None

    # Should raise HTTPException with 400 status
    with pytest.raises(HTTPException) as exc_info:
        await check_user_can_run_task(context)

    assert exc_info.value.status_code == 400
    assert (
        "User information not available for permission check"
        in exc_info.value.detail
    )


@pytest.mark.asyncio
@patch(APP_STATE)
async def test_check_user_can_run_task_invalid_user_id(
    mock_app_state: AsyncMock,
) -> None:
    """Test permission check when user_id is invalid.

    Parameters
    ----------
    mock_app_state : AsyncMock
        Mock for the app_state fixture.
    """

    # Mock settings
    mock_settings = AsyncMock()
    mock_settings.enable_external_auth = True
    mock_settings.task_permission_verify_url = "https://api.example.com/check"
    mock_settings.task_permission_secret = "test-secret"  # nosec
    mock_app_state.settings = mock_settings

    # Create context with invalid user info
    context = RequestContext()
    context.external_user_info = {"sub": None, "id": ""}

    # Should raise HTTPException with 400 status
    with pytest.raises(HTTPException) as exc_info:
        await check_user_can_run_task(context)

    assert exc_info.value.status_code == 400
    assert (
        "Invalid user identifier for permission check" in exc_info.value.detail
    )


@pytest.mark.asyncio
@patch(APP_STATE)
@patch(HTTPX_ASYNC_CLIENT)
async def test_check_user_can_run_task_permission_granted(
    mock_client_class: AsyncMock,
    mock_app_state: AsyncMock,
) -> None:
    """Test permission check when permission is granted.

    Parameters
    ----------
    mock_client_class : AsyncMock
        Mock for the httpx.AsyncClient class.
    mock_app_state : AsyncMock
        Mock for the app_state fixture.
    """

    # Mock settings
    mock_settings = AsyncMock()
    mock_settings.enable_external_auth = True
    mock_settings.task_permission_verify_url = "https://api.example.com/check"
    mock_settings.task_permission_secret = "test-secret"  # nosec
    mock_app_state.settings = mock_settings

    # Mock HTTP client
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"can_run": True}
    mock_client.get.return_value = mock_response
    mock_client_class.return_value.__aenter__.return_value = mock_client

    # Create context with user info
    context = RequestContext()
    context.external_user_info = {"sub": "user123", "id": "user123"}

    # Should not raise any exception
    await check_user_can_run_task(context)

    # Verify the request was made correctly
    mock_client.get.assert_called_once_with(
        "https://api.example.com/check",
        params={"user_id": "user123"},
        headers={"X-Runner-Secret-Key": "test-secret"},
        timeout=10.0,
    )


@pytest.mark.asyncio
@patch(APP_STATE)
@patch(HTTPX_ASYNC_CLIENT)
async def test_check_user_can_run_task_permission_denied(
    mock_client_class: AsyncMock,
    mock_app_state: AsyncMock,
) -> None:
    """Test permission check when permission is denied.

    Parameters
    ----------
    mock_client_class : AsyncMock
        Mock for the httpx.AsyncClient class.
    mock_app_state : AsyncMock
        Mock for the app_state fixture.
    """

    # Mock settings
    mock_settings = AsyncMock()
    mock_settings.enable_external_auth = True
    mock_settings.task_permission_verify_url = "https://api.example.com/check"
    mock_settings.task_permission_secret = "test-secret"  # nosec
    mock_app_state.settings = mock_settings

    # Mock HTTP client to simulate 429 response

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.json.return_value = {
        "can_run": False,
        "reason": "User quota exceeded",
    }
    mock_client.get.side_effect = HTTPStatusError(
        "429 Client Error", request=MagicMock(), response=mock_response
    )
    mock_client_class.return_value.__aenter__.return_value = mock_client

    # Create context with user info
    context = RequestContext()
    context.external_user_info = {"sub": "user123"}

    # Should raise HTTPException with 429 status
    with pytest.raises(HTTPException) as exc_info:
        await check_user_can_run_task(context)

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "User quota exceeded"


@pytest.mark.asyncio
@patch(APP_STATE)
@patch(HTTPX_ASYNC_CLIENT)
async def test_check_user_can_run_task_http_error(
    mock_client_class: AsyncMock,
    mock_app_state: AsyncMock,
) -> None:
    """Test permission check when HTTP request fails.

    Parameters
    ----------
    mock_client_class : AsyncMock
        Mock for the httpx.AsyncClient class.
    mock_app_state : AsyncMock
        Mock for the app_state fixture.
    """

    # Mock settings
    mock_settings = AsyncMock()
    mock_settings.enable_external_auth = True
    mock_settings.task_permission_verify_url = "https://api.example.com/check"
    mock_settings.task_permission_secret = "test-secret"  # nosec
    mock_app_state.settings = mock_settings

    # Mock HTTP client to raise HTTPStatusError
    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("HTTP Error")
    mock_client_class.return_value.__aenter__.return_value = mock_client

    # Create context with user info
    context = RequestContext()
    context.external_user_info = {"sub": "user123"}

    # Should raise HTTPException with 500 status
    with pytest.raises(HTTPException) as exc_info:
        await check_user_can_run_task(context)

    assert exc_info.value.status_code == 500
    assert "Failed to verify user permission" in exc_info.value.detail


@pytest.mark.asyncio
@patch(APP_STATE)
@patch(HTTPX_ASYNC_CLIENT)
async def test_check_user_can_run_task_invalid_json(
    mock_client_class: AsyncMock,
    mock_app_state: AsyncMock,
) -> None:
    """Test permission check when response is not valid JSON.

    Parameters
    ----------
    mock_client_class : AsyncMock
        Mock for the httpx.AsyncClient class.
    mock_app_state : AsyncMock
        Mock for the app_state fixture.
    """

    # Mock settings
    mock_settings = AsyncMock()
    mock_settings.enable_external_auth = True
    mock_settings.task_permission_verify_url = "https://api.example.com/check"
    mock_settings.task_permission_secret = "test-secret"  # nosec
    mock_app_state.settings = mock_settings

    # Mock HTTP client
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_client.get.return_value = mock_response
    mock_client_class.return_value.__aenter__.return_value = mock_client

    # Create context with user info
    context = RequestContext()
    context.external_user_info = {"sub": "user123"}

    # Should raise HTTPException with 500 status
    with pytest.raises(HTTPException) as exc_info:
        await check_user_can_run_task(context)

    assert exc_info.value.status_code == 500
    assert "Invalid response from permission check" in exc_info.value.detail


@pytest.mark.asyncio
@patch(APP_STATE)
@patch(HTTPX_ASYNC_CLIENT)
async def test_check_user_can_run_task_user_id_from_id_field(
    mock_client_class: AsyncMock,
    mock_app_state: AsyncMock,
) -> None:
    """Test permission check when user_id comes from 'id' field.

    Parameters
    ----------
    mock_client_class : AsyncMock
        Mock for the httpx.AsyncClient class.
    mock_app_state : AsyncMock
        Mock for the app_state fixture.
    """

    # Mock settings
    mock_settings = AsyncMock()
    mock_settings.enable_external_auth = True
    mock_settings.task_permission_verify_url = "https://api.example.com/check"
    mock_settings.task_permission_secret = "test-secret"  # nosec
    mock_app_state.settings = mock_settings

    # Mock HTTP client
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"can_run": True}
    mock_client.get.return_value = mock_response
    mock_client_class.return_value.__aenter__.return_value = mock_client

    # Create context with user info using 'id' field
    context = RequestContext()
    context.external_user_info = {"id": "user456"}

    # Should not raise any exception
    await check_user_can_run_task(context)

    # Verify the request was made with the correct user_id
    mock_client.get.assert_called_once_with(
        "https://api.example.com/check",
        params={"user_id": "user456"},
        headers={"X-Runner-Secret-Key": "test-secret"},
        timeout=10.0,
    )


@pytest.mark.asyncio
@patch(APP_STATE)
@patch(HTTPX_ASYNC_CLIENT)
async def test_check_user_can_run_task_sub_takes_precedence(
    mock_client_class: AsyncMock,
    mock_app_state: AsyncMock,
) -> None:
    """Test that 'sub' field takes precedence over 'id' field.

    Parameters
    ----------
    mock_client_class : AsyncMock
        Mock for the httpx.AsyncClient class.
    mock_app_state : AsyncMock
        Mock for the app_state fixture.
    """

    # Mock settings
    mock_settings = AsyncMock()
    mock_settings.enable_external_auth = True
    mock_settings.task_permission_verify_url = "https://api.example.com/check"
    mock_settings.task_permission_secret = "test-secret"  # nosec
    mock_app_state.settings = mock_settings

    # Mock HTTP client
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"can_run": True}
    mock_client.get.return_value = mock_response
    mock_client_class.return_value.__aenter__.return_value = mock_client

    # Create context with both 'sub' and 'id' fields
    context = RequestContext()
    context.external_user_info = {"sub": "user_from_sub", "id": "user_from_id"}

    # Should not raise any exception
    await check_user_can_run_task(context)

    # Verify the request was made with 'sub' value
    mock_client.get.assert_called_once_with(
        "https://api.example.com/check",
        params={"user_id": "user_from_sub"},
        headers={"X-Runner-Secret-Key": "test-secret"},
        timeout=10.0,
    )
