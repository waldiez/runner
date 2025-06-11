# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Custom middlewares for the waldiez_runner project."""

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from .conditional_gzip import ConditionalGZipMiddleware
from .extra_headers import ExtraHeadersMiddleware
from .slow_api import add_rate_limiter, limiter

if TYPE_CHECKING:
    from waldiez_runner.config import Settings


EXCLUDE_PATTERNS = [
    r"^/api/v1/tasks/.+/download$",
]


def add_middlewares(app: FastAPI, settings: "Settings") -> None:
    """Add middlewares to the FastAPI app.

    Parameters
    ----------
    app : FastAPI
        The FastAPI app
    settings : Settings
        The settings
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.trusted_origins,
        allow_origin_regex=settings.trusted_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        ProxyHeadersMiddleware,  # type: ignore
        trusted_hosts=settings.trusted_hosts,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts,
        www_redirect=False,
    )
    app.add_middleware(
        ConditionalGZipMiddleware,
        exclude_patterns=EXCLUDE_PATTERNS,
        minimum_size=1000,
        compresslevel=9,
    )
    app.add_middleware(
        ExtraHeadersMiddleware,
        exclude_patterns=EXCLUDE_PATTERNS,
        csp=not settings.dev,
        force_ssl=settings.force_ssl,
    )
    add_rate_limiter(app)


__all__ = ["add_middlewares", "limiter"]
