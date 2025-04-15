# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=too-many-try-statements,broad-exception-caught

"""Waldiez serve client."""

import asyncio
import inspect
from types import TracebackType
from typing import Any, Callable, Coroutine, Type

from typing_extensions import Self

from .auth import Auth


class BaseClient:
    """Base client class."""

    def __init__(
        self,
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        on_auth_token: (
            Callable[[str], None]
            | Callable[[str], Coroutine[Any, Any, None]]
            | None
        ) = None,
        on_auth_error: (
            Callable[[str], None]
            | Callable[[str], Coroutine[Any, Any, None]]
            | None
        ) = None,
        on_error: (
            Callable[[str], None]
            | Callable[[str], Coroutine[Any, Any, None]]
            | None
        ) = None,
    ) -> None:
        """Initialize the base client with optional late configuration.

        Parameters
        ----------
        base_url : str | None, optional
            The base URL, by default None
        client_id : str | None, optional
            The client ID, by default None
        client_secret : str | None, optional
            The client secret, by default None
        on_auth_token : Callable[[str], None]
                      | Callable[[str], Coroutine[Any, Any, None]]
                      | None, optional
            The function to call on token retrieval, by default None
        on_auth_error : Callable[[str], None]
                      | Callable[[str], Coroutine[Any, Any, None]]
                      | None, optional
            The function to call on auth error, by default None
        on_error : Callable[[str], None]
                  | Callable[[str], Coroutine[Any, Any, None]]
                  | None, optional
            A generic error handler for API-related errors.
            Can be used by subclasses (e.g. TaskClient, ClientAdmin).
        """
        self.base_url: str | None = base_url
        self.client_id: str | None = client_id
        self.client_secret: str | None = client_secret
        self.auth: Auth | None = None
        self.on_auth_token = on_auth_token
        self.on_auth_error = on_auth_error
        self.on_error = on_error
        if base_url and client_id and client_secret:
            self.configure(
                base_url=base_url,
                client_id=client_id,
                client_secret=client_secret,
                on_auth_token=on_auth_token,
                on_auth_error=on_auth_error,
            )

    async def __aenter__(self) -> Self:
        """Enter context for async usage.

        Returns
        -------
        Client
            The client instance
        """
        self._ensure_configured()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit context for async usage, ensuring cleanup.

        Parameters
        ----------
        exc_type : Type[BaseException] | None
            The exception type
        exc_value : BaseException | None
            The exception value
        traceback : TracebackType | None
            The traceback
        """
        await self.aclose()

    def __enter__(self) -> Self:
        """Enter context for sync usage."""
        self._ensure_configured()
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit context for sync usage, ensuring cleanup.

        Parameters
        ----------
        exc_type : Type[BaseException] | None
            The exception type
        exc_value : BaseException | None
            The exception value
        traceback : TracebackType | None
            The traceback
        """
        self.close()

    def close(self) -> None:
        """Close the client properly."""
        # should be overridden in subclasses

    async def aclose(self) -> None:
        """Async version of close method."""
        # should be overridden in subclasses

    def configure(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        on_auth_token: (
            Callable[[str], None]
            | Callable[[str], Coroutine[Any, Any, None]]
            | None
        ) = None,
        on_auth_error: (
            Callable[[str], None]
            | Callable[[str], Coroutine[Any, Any, None]]
            | None
        ) = None,
        on_error: (
            Callable[[str], None]
            | Callable[[str], Coroutine[Any, Any, None]]
            | None
        ) = None,
    ) -> None:
        """Configure the authentication and task API client.

        Parameters
        ----------
        base_url : str
            The base URL
        client_id : str
            The client ID
        client_secret : str
            The client secret
        on_auth_token : Callable[[str], None]
                      | Callable[[str], Coroutine[Any, Any, None]]
                      | None, optional
            The function to call on token retrieval, by default None
        on_auth_error : Callable[[str], None]
                      | Callable[[str], Coroutine[Any, Any, None]]
                      | None, optional
            The function to call on auth error, by default None
        on_error : Callable[[str], None]
                 | Callable[[str], Coroutine[Any, Any, None]]
                 | None, optional
            The function to call on tasks API error, by default None
        """
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.on_auth_token = on_auth_token or self.on_auth_token
        self.on_auth_error = on_auth_error or self.on_auth_error
        self.on_error = on_error or self.on_error
        self.auth = Auth(
            base_url=base_url,
            on_error=self.on_auth_error,
            on_token=self.on_auth_token,
        )
        self.auth.configure(client_id, client_secret, base_url=base_url)

    def has_valid_token(self) -> bool:
        """Check if the client has an auth token.

        Returns
        -------
        bool
            Whether the client has a valid token
        """
        if not self.auth:  # pragma: no cover
            return False
        return self.auth.has_valid_token()

    def authenticate(self) -> bool:
        """Authenticate the client.

        Returns
        -------
        bool
            Whether the client was authenticated successfully or not.
        """
        if (
            not self.auth
            or not self.auth.base_url
            or not self.auth.client_id
            or not self.auth.client_secret
        ):
            return False  # pragma: no cover
        # pylint: disable=broad-exception-caught
        try:
            self.auth.sync_get_token()
            return True
        except BaseException as err:  # pragma: no cover
            self._handle_auth_error(f"Error authenticating: {err}")
            return False

    async def a_authenticate(self) -> bool:
        """Authenticate the client asynchronously.

        Returns
        -------
        bool
            Whether the client was authenticated successfully or not.
        """
        if (
            not self.auth
            or not self.auth.base_url
            or not self.auth.client_id
            or not self.auth.client_secret
        ):
            return False  # pragma: no cover
        # pylint: disable=broad-exception-caught
        try:
            await self.auth.async_get_token()
            return True
        except BaseException as err:  # pragma: no cover
            self._handle_auth_error(f"Error authenticating: {err}")
            return False

    def _handle_auth_error(self, message: str) -> None:
        """Handle authentication errors.

        Parameters
        ----------
        message : str
            The error message to pass to the handler
        """
        if self.on_auth_error:  # pragma: no branch
            if inspect.iscoroutinefunction(self.on_auth_error):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.on_auth_error(message))
                except RuntimeError:  # pragma: no cover
                    asyncio.run(self.on_auth_error(message))
            else:
                self.on_auth_error(message)

    def _handle_error(self, message: str) -> None:
        """Handle API error.

        Parameters
        ----------
        message : str
            The error message to pass to the handler
        """
        if self.on_error:  # pragma: no branch
            if inspect.iscoroutinefunction(self.on_error):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.on_error(message))
                except RuntimeError:
                    asyncio.run(self.on_error(message))
            else:
                self.on_error(message)

    def _ensure_configured(self) -> None:
        """Ensure the client is configured before use.

        Raises
        ------
        ValueError
            If the client is not configured
        """
        if not self.auth:
            raise ValueError(
                "Client is not configured. Call `configure()` first."
            )
