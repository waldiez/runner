# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Middleware for rate limiting."""

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIASGIMiddleware
from slowapi.util import get_remote_address


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


limiter = Limiter(key_func=get_real_ip)


def add_rate_limiter(app: FastAPI) -> None:
    """Add rate limits to the app.

    Parameters
    ----------
    app : FastAPI
        The app
    """
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore
    )
    app.add_middleware(SlowAPIASGIMiddleware)
