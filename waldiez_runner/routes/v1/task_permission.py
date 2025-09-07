# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pylint: disable=too-many-lines
# pyright: reportPossiblyUnboundVariable=false

"""Task router helpers."""

import logging
from typing import Any, cast

import httpx
from fastapi import HTTPException
from starlette import status

from waldiez_runner.config.settings import Settings
from waldiez_runner.dependencies import app_state
from waldiez_runner.dependencies.context import (
    RequestContext,
)

LOG = logging.getLogger(__name__)


async def check_user_can_run_task(context: RequestContext) -> None:
    """Check if the user is allowed to run a task.

    Parameters
    ----------
    context : RequestContext
        The request context containing external user info.

    Raises
    ------
    HTTPException
        If the user is not allowed to run the task or if the check fails.
    """

    _validate_settings()
    settings = cast(Settings, app_state.settings)

    if not settings.enable_external_auth:
        return

    if not _is_permission_check_configured(settings):
        return

    user_id = _extract_user_id(context)
    await _verify_user_permission(settings, user_id)


def _validate_settings() -> None:
    """Validate that application settings are initialized."""
    if not app_state.settings:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Settings not initialized",
        )


def _is_permission_check_configured(settings: Settings) -> bool:
    """Check if permission verification is properly configured."""
    verify_url = settings.task_permission_verify_url
    secret = settings.task_permission_secret

    if not verify_url or not secret:
        LOG.warning("External auth verify URL or secret not configured")
        return False
    return True


def _extract_user_id(context: RequestContext) -> str:
    """Extract user ID from the request context."""
    if not context.external_user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User information not available for permission check",
        )

    user_id = context.external_user_info.get(
        "sub"
    ) or context.external_user_info.get("id")

    if not user_id or not isinstance(user_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user identifier for permission check",
        )

    return user_id


async def _verify_user_permission(settings: Settings, user_id: str) -> None:
    """Verify user permission by making an HTTP request."""
    try:
        data = await _make_permission_request(settings, user_id)
        # Assuming server returns 200 only if can_run is true
        # If can_run is false, server returns 429
    except HTTPException:
        # Re-raise HTTPException instances (like 429 errors)
        # without wrapping them
        raise
    except httpx.HTTPStatusError as error:
        if error.response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            try:
                data = error.response.json()
                reason = data.get("reason", "Too many requests")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=reason,
                ) from error
            except (ValueError, KeyError):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests",
                ) from error
        LOG.error(
            "Permission check failed with status %s", error.response.status_code
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify user permission",
        ) from error
    except ValueError as error:
        LOG.error("Invalid JSON response from permission check: %s", error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid response from permission check",
        ) from error
    except Exception as error:
        LOG.error("Unexpected error during permission check: %s", error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify user permission",
        ) from error


async def _make_permission_request(
    settings: Settings, user_id: str
) -> dict[str, Any]:
    """Make the HTTP request to verify user permission."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            settings.task_permission_verify_url,
            params={"user_id": user_id},
            headers={"X-Runner-Secret-Key": settings.task_permission_secret},
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()
