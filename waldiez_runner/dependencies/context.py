# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Request context dependencies."""

from typing import Any, Dict, Optional

from fastapi import Request


# pylint: disable=too-few-public-methods
class RequestContext:
    """Request context for storing state during request processing."""

    external_user_info: Optional[Dict[str, Any]]
    is_external_auth: bool

    def __init__(self) -> None:
        """Initialize an empty context."""
        self.external_user_info = None
        self.is_external_auth = False


async def get_request_context(request: Request) -> RequestContext:
    """Get or create a RequestContext for the current request.

    Parameters
    ----------
    request : Request
        The current request

    Returns
    -------
    RequestContext
        The request context
    """
    if not hasattr(request.state, "context"):
        request.state.context = RequestContext()
    return request.state.context
