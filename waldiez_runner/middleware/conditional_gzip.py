# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Custom GZip middleware to exclude certain patterns from compression."""

import re
from typing import List, Optional

from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


# pylint: disable=too-few-public-methods
class ConditionalGZipMiddleware:
    """Custom GZip middleware to exclude certain patterns from compression."""

    def __init__(
        self,
        app: ASGIApp,
        exclude_patterns: Optional[List[str]] = None,
        minimum_size: int = 500,
        compresslevel: int = 5,
    ) -> None:
        """Initialize the middleware.

        Parameters
        ----------
        app : ASGIApp
            The ASGI app
        exclude_patterns: List[str], optional
            List of regex patterns to exclude from compression
        minimum_size : int, optional
            Minimum size of the response to be compressed
        compresslevel : int, optional
            Compression level for GZip
        """
        self.exclude_patterns = [
            re.compile(p) for p in (exclude_patterns or [])
        ]
        self.gzip = GZipMiddleware(
            app, minimum_size=minimum_size, compresslevel=compresslevel
        )
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Call the middleware.

        Parameters
        ----------
        scope : Scope
            The ASGI scope
        receive : Receive
            The ASGI receive channel
        send : Send
            The ASGI send channel
        """
        path = scope.get("path", "")
        if scope["type"] == "http" and any(
            p.search(path) for p in self.exclude_patterns
        ):
            # bypass the GZip middleware
            # if the path matches any of the patterns
            await self.app(scope, receive, send)
        else:
            await self.gzip(scope, receive, send)
