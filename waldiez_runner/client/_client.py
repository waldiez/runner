# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# flake8: noqa: E501
# pylint: disable=line-too-long,too-many-try-statements,broad-exception-caught

"""Waldiez serve client."""

import asyncio
import inspect
import json
from io import BytesIO
from types import TracebackType
from typing import Any, Callable, Coroutine, Dict, Type

from ._auth import CustomAuth
from ._tasks_api import TasksAPIClient
from ._websockets import AsyncWebSocketClient, SyncWebSocketClient


# pylint: disable=too-many-public-methods
class Client:
    """Waldiez serve client."""

    def __init__(
        self,
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        on_auth_token: Callable[[str], None] | None = None,
        on_auth_error: Callable[[str], None] | None = None,
        on_tasks_error: (
            Callable[[str], None]
            | Callable[[str], Coroutine[Any, Any, None]]
            | None
        ) = None,
    ) -> None:
        """Initialize the unified client with late configuration."""
        self.base_url: str | None = base_url
        self.client_id: str | None = client_id
        self.client_secret: str | None = client_secret

        self.auth: CustomAuth | None = None
        self.tasks: TasksAPIClient | None = None
        self.ws_sync: SyncWebSocketClient | None = None
        self.ws_async: AsyncWebSocketClient | None = None
        self.on_auth_token = on_auth_token
        self.on_auth_error = on_auth_error
        self.on_tasks_error = on_tasks_error
        if base_url and client_id and client_secret:
            self.configure(
                base_url=base_url,
                client_id=client_id,
                client_secret=client_secret,
                on_auth_token=on_auth_token,
                on_auth_error=on_auth_error,
                on_tasks_error=on_tasks_error,
            )

    def __enter__(self) -> "Client":
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

    async def __aenter__(self) -> "Client":
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

    def configure(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        on_auth_token: Callable[[str], None] | None = None,
        on_auth_error: Callable[[str], None] | None = None,
        on_tasks_error: (
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
        on_auth_token : Callable[[str], None], optional
            The function to call on token retrieval, by default None
        on_auth_error : Callable[[str], None], optional
            The function to call on auth error, by default None
        on_tasks_error : Callable[[str], None] | Callable[[str], Coroutine[Any, Any, None]] | None, optional
            The function to call on tasks API error, by default None
        """
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        if on_tasks_error:
            self.on_tasks_error = on_tasks_error
        _on_auth_token = on_auth_token or self.on_auth_token
        _on_auth_error = on_auth_error or self.on_auth_error
        self.auth = CustomAuth(
            base_url=base_url,
            on_error=_on_auth_error,
            on_token=_on_auth_token,
        )
        self.auth.configure(client_id, client_secret, base_url=base_url)
        if client_id and client_secret:
            self.tasks = TasksAPIClient(
                self.auth,
                on_error=self._handle_tasks_error,
            )
            self.ws_sync = SyncWebSocketClient(self.auth)
            self.ws_async = AsyncWebSocketClient(self.auth)

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
            return False
        try:
            self.auth.sync_get_token()
            return True
        except BaseException:
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
            return False
        try:
            await self.auth.async_get_token()
            return True
        except BaseException:
            return False

    def has_valid_token(self) -> bool:
        """Check if the client has an auth token.

        Returns
        -------
        bool
            Whether the client has a valid token
        """
        if not self.auth:
            return False
        return self.auth.has_valid_token()

    def _handle_tasks_error(self, message: str) -> None:
        """Handle tasks API errors.

        Parameters
        ----------
        message : str
            The error message to pass to the handler
        """
        if self.on_tasks_error:
            if inspect.iscoroutinefunction(self.on_tasks_error):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.on_tasks_error(message))
                except RuntimeError:
                    asyncio.run(self.on_tasks_error(message))
            else:
                self.on_tasks_error(message)

    def _ensure_configured(self) -> None:
        """Ensure the client is configured before use.

        Raises
        ------
        ValueError
            If the client is not configured
        """
        if not self.auth or not self.tasks:
            raise ValueError(
                "Client is not configured. Call `configure()` first."
            )

    def trigger_task(
        self, file_data: bytes, file_name: str, input_timeout: int = 180
    ) -> Dict[str, Any]:
        """Trigger a new task synchronously.

        Parameters
        ----------
        file_data : bytes
            The file data
        file_name : str
            The file name
        input_timeout : int, optional
            The input timeout in seconds, by default 180

        Returns
        -------
        Dict[str, Any]
            The response JSON

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        return self.tasks.trigger_task(  # type: ignore
            file_data,
            file_name,
            input_timeout=input_timeout,
        )

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Retrieve the status of a task synchronously.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        Dict[str, Any]
            The response JSON

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        return self.tasks.get_task_status(task_id)  # type: ignore

    def send_user_input(
        self,
        task_id: str,
        user_input: str,
        request_id: str,
        use_rest: bool = False,
    ) -> None:
        """Send user input to a task synchronously.

        Parameters
        ----------
        task_id : str
            The task ID
        user_input : str
            The user input
        request_id : str
            The request ID
        use_rest : bool, optional
            Whether to use REST API, by default False

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        sent = False
        if use_rest is False:
            # first check/try using websockets
            if self.ws_sync and self.ws_sync.is_listening():
                message = {
                    "data": user_input,
                    "request_id": request_id,
                }
                try:
                    self.ws_sync.send(task_id, json.dumps(message))
                    sent = True
                except BaseException as e:
                    self._handle_tasks_error(
                        f"Error sending user input via WebSocket: {e}"
                    )
        if not sent:
            self.tasks.send_user_input(  # type: ignore
                task_id=task_id,
                user_input=user_input,
                request_id=request_id,
            )

    def download_task_results(self, task_id: str) -> bytes:
        """Download a completed task's results archive.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        bytes
            The results archive

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        return self.tasks.download_task_results(task_id)  # type: ignore

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel or delete a task synchronously.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        Dict[str, Any]
            The response JSON

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        return self.tasks.cancel_task(task_id)  # type: ignore

    async def a_trigger_task(
        self,
        file_data: BytesIO,
        file_name: str,
        input_timeout: int = 180,
    ) -> Dict[str, Any]:
        """Trigger a new task asynchronously.

        Parameters
        ----------
        file_data : BytesIO
            The file data
        file_name : str
            The file name
        input_timeout : int, optional
            The input timeout in seconds, by default 180

        Returns
        -------
        Dict[str, Any]
            The response JSON

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        return await self.tasks.a_trigger_task(  # type: ignore
            file_data,  # type: ignore
            file_name,
            input_timeout=input_timeout,
        )

    async def a_get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Retrieve the status of a task asynchronously.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        Dict[str, Any]
            The response JSON

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        return await self.tasks.a_get_task_status(task_id)  # type: ignore

    async def a_send_user_input(
        self,
        task_id: str,
        user_input: str,
        request_id: str,
        use_rest: bool = False,
    ) -> None:
        """Send user input to a task asynchronously.

        Parameters
        ----------
        task_id : str
            The task ID
        user_input : str
            The user input
        request_id : str
            The request ID
        use_rest : bool, optional
            Whether to use REST API, by default False

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        sent = False
        if use_rest is False:
            # first check/try using websockets
            if self.ws_async and self.ws_async.is_listening():
                try:
                    message = {
                        "data": user_input,
                        "request_id": request_id,
                    }
                    await self.ws_async.send(task_id, json.dumps(message))
                    sent = True
                except BaseException as e:
                    self._handle_tasks_error(
                        f"Error sending user input via WebSocket: {e}"
                    )
        if not sent:
            await self.tasks.a_send_user_input(  # type: ignore
                task_id=task_id,
                user_input=user_input,
                request_id=request_id,
            )

    async def a_download_task_results(self, task_id: str) -> BytesIO:
        """Download a completed task's result archive asynchronously as BytesIO.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        BytesIO
            The results archive as BytesIO

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        return await self.tasks.a_download_task_results(task_id)  # type: ignore

    async def a_cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel or delete a task asynchronously.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        Dict[str, Any]
            The response JSON

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        return await self.tasks.a_cancel_task(task_id)  # type: ignore

    def is_listening(self) -> bool:
        """Check if the WebSocket listener is running.

        Returns
        -------
        bool
            Whether the WebSocket listener is running
        """
        if self.ws_sync:
            return self.ws_sync.is_listening()
        return False

    def start_ws_listener(
        self,
        task_id: str,
        on_message: Callable[[str], None],
        on_error: Callable[[str], None] | None = None,
        in_thread: bool = True,
    ) -> None:
        """Start listening to the WebSocket (sync).

        Parameters
        ----------
        task_id: str
            The task ID to use for the WebSocket connection
        on_message : Callable[[str], None]
            The function to call when a message is received
        on_error : Callable[[str], None], optional
            The function to call on error, by default None
        in_thread : bool, optional
            Whether to run in a thread, by default True

        Raises
        ------
        ValueError
            If the WebSocket client is not configured
        """
        if not self.ws_sync:
            raise ValueError(
                "WebSockets are not configured. Call `configure()` first."
            )
        if self.is_listening():
            return
        self.ws_sync.listen(
            task_id=task_id,
            on_message=on_message,
            on_error=on_error,
            in_thread=in_thread,
        )

    async def a_is_listening(self) -> bool:
        """Check if the WebSocket listener is running asynchronously.

        Returns
        -------
        bool
            Whether the WebSocket listener is running
        """
        if self.ws_async:
            return self.ws_async.is_listening()
        return False

    async def start_ws_async_listener(
        self,
        task_id: str,
        on_message: Callable[[str], Coroutine[Any, Any, None]],
        on_error: Callable[[str], Coroutine[Any, Any, None]] | None = None,
        in_task: bool = True,
    ) -> None:
        """Start listening to the WebSocket (async).

        Parameters
        ----------
        task_id : str
            The task ID to use for the WebSocket connection
        on_message : Callable[[str], Coroutine[Any, Any, None]]
            The function to call when a message is received
        on_error : Callable[[str], Coroutine[Any, Any, None]], optional
            The function to call on error, by default None
        in_task : bool, optional
            Whether to run in a task, by default True

        Raises
        ------
        ValueError
            If the WebSocket client is not configured
        """
        if not self.ws_async:
            raise ValueError(
                "WebSockets are not configured. Call `configure()` first."
            )
        if await self.a_is_listening():
            return
        await self.ws_async.listen(
            task_id=task_id,
            on_message=on_message,
            on_error=on_error,
            in_task=in_task,
        )

    def stop_ws_listener(self) -> None:
        """Stop the WebSocket listener (sync)."""
        if self.ws_sync:
            self.ws_sync.stop()

    async def stop_ws_async_listener(self) -> None:
        """Stop the WebSocket listener (async)."""
        if self.ws_async:
            await self.ws_async.stop()

    def close(self) -> None:
        """Close all clients properly."""
        if self.ws_sync:
            self.ws_sync.stop()
        if self.ws_async:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.ws_async.stop())
            except RuntimeError:
                asyncio.run(self.ws_async.stop())

    async def aclose(self) -> None:
        """Async close for WebSocket and tasks."""
        if self.ws_async:
            await self.ws_async.stop()
        if self.ws_sync:
            self.ws_sync.stop()
