# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Base class to inherit from for all API clients."""

import asyncio
import inspect
from typing import Any, Callable, Coroutine

from .auth import Auth


class BaseAPIClient:
    """Base class for API clients.

    Attributes
    ----------
    auth : CustomAuth | None
        The authentication object
    on_error : Callable[[str], None]
             | Callable[[str], Coroutine[Any, Any, None]]
             | None
        The function to call on error, by default None
    """

    def __init__(
        self,
        auth: Auth | None,
        on_error: (
            Callable[[str], None]
            | Callable[[str], Coroutine[Any, Any, None]]
            | None
        ) = None,
    ) -> None:
        """Initialize the client.

        Parameters
        ----------
        auth : CustomAuth | None
            The authentication object
        on_error : Callable[[str], None]
                 | Callable[[str], Coroutine[Any, Any, None]] | None
            The function to call on error, by default None
            If None, the error will be raised.

        Raises
        ------
        ValueError
            If the base URL is not set in the auth object
        """
        self._auth = auth
        self.on_error = on_error
        if auth:
            self.configure(auth)

    def configure(self, auth: Auth) -> None:
        """Configure the client.

        Parameters
        ----------
        auth : CustomAuth
            The authentication object

        Raises
        ------
        ValueError
            If the base URL is not set in the auth object
        """
        self._auth = auth
        if not auth.base_url:
            raise ValueError("Base URL is required")
        if not self.on_error and auth.on_error:  # pragma: no cover
            self.on_error = auth.on_error

    def ensure_configured(self) -> None:
        """Ensure the client is configured.

        Raises
        ------
        ValueError
            If the client is not configured
        """
        if not self._auth or not self._auth.base_url:
            raise ValueError("Client is not configured")

    def handle_error(self, message: str) -> None:
        """Handle an error.

        Parameters
        ----------
        message : str
            The error message
        """
        if self.on_error:
            if inspect.iscoroutinefunction(self.on_error):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.on_error(message))
                except RuntimeError:  # pragma: no cover
                    asyncio.run(self.on_error(message))
            else:
                self.on_error(message)
