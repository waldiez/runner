# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pyright: reportArgumentType=false
"""Middleware for rate limiting."""

import re

from fastapi import FastAPI, Request

# noinspection PyProtectedMember
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIASGIMiddleware
from slowapi.util import get_remote_address
from starlette.types import ASGIApp, Receive, Scope, Send


def get_real_ip(request: Request) -> str:
    """Guess the IP of the client.

    Parameters
    ----------
    request : Request
        The request

    Returns
    -------
    str
        The guessed IP
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return get_remote_address(request)


# pylint: disable=too-few-public-methods
class SlowAPIMiddleware:
    """Custom SlowAPI MIddleware."""

    def __init__(
        self,
        app: ASGIApp,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        """Initialize the instance."""
        self.app = app
        self._slow = SlowAPIASGIMiddleware(app=app)
        self.exclude_patterns = [
            re.compile(p) for p in (exclude_patterns or [])
        ]

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Call the middleware."""
        path = scope.get("path", "")
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if any(p.match(path) for p in self.exclude_patterns):
            # bypass the middleware
            return await self.app(scope, receive, send)
        await self._slow(scope=scope, receive=receive, send=send)


def add_rate_limiter(
    app: FastAPI, exclude_patterns: list[str] | None = None
) -> Limiter:
    """Add rate limits to the app.

    Parameters
    ----------
    app : FastAPI
        The app
    exclude_patterns : Optional[list[str]]
        Patterns to exclude.

    Returns
    -------
    Limiter
        The slowapi's Limiter.
    """
    limiter = Limiter(key_func=get_real_ip)
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore
    )
    app.add_middleware(SlowAPIMiddleware, exclude_patterns)
    return limiter
