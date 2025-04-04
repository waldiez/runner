# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Custom middlewares for the waldiez_runner project."""

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from .extra_headers import ExtraHeadersMiddleware
from .limiter import add_rate_limiter

if TYPE_CHECKING:
    from waldiez_runner.config import Settings


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
        ProxyHeadersMiddleware,
        trusted_hosts=settings.trusted_hosts,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts,
        www_redirect=False,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        ExtraHeadersMiddleware,
        csp=not settings.dev,
        force_ssl=settings.force_ssl,
    )
    add_rate_limiter(app)


__all__ = ["add_middlewares"]
