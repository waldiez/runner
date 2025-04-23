# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Waldiez serve tasks client."""

import asyncio
import json
from io import BytesIO
from typing import Any, Callable, Coroutine, Dict, List

from ._tasks_api import TasksAPIClient
from ._websockets import AsyncWebSocketClient, SyncWebSocketClient
from .client_base import BaseClient
from .models import (
    TaskCreateRequest,
    TaskItemsRequest,
    TaskItemsResponse,
    TaskResponse,
    TaskUpdateRequest,
    UserInputRequest,
)


# pylint: disable=too-many-public-methods
class TasksClient(BaseClient):
    """Tasks client implementation."""

    tasks: TasksAPIClient | None
    ws_sync: SyncWebSocketClient | None
    ws_async: AsyncWebSocketClient | None

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
        """Initialize the tasks client with optional late configuration."""
        self.tasks = None
        self.ws_sync = None
        self.ws_async = None
        super().__init__(
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
            on_auth_token=on_auth_token,
            on_auth_error=on_auth_error,
            on_error=on_error,
        )

    def close(self) -> None:
        """Close the client properly."""
        if self.ws_sync:
            self.ws_sync.stop()
        if self.ws_async:  # pragma: no branch
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.ws_async.stop())  # pragma: no cover
            except RuntimeError:
                asyncio.run(self.ws_async.stop())

    async def aclose(self) -> None:
        """Async close for WebSocket and tasks."""
        if self.ws_async:  # pragma: no branch
            await self.ws_async.stop()
        if self.ws_sync:  # pragma: no branch
            self.ws_sync.stop()
        self.ws_sync = None
        self.ws_async = None
        self.tasks = None

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
            The function to call on tasks API error,
            by default None (or self.on_error)
        """
        super().configure(
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
            on_auth_token=on_auth_token,
            on_auth_error=on_auth_error,
            on_error=on_error,
        )
        if client_id and client_secret and self.auth:
            self.tasks = TasksAPIClient(
                self.auth,
                on_error=self._handle_error,
            )
            self.ws_sync = SyncWebSocketClient(self.auth)
            self.ws_async = AsyncWebSocketClient(self.auth)

    def _ensure_configured(self) -> None:
        super()._ensure_configured()
        if not self.tasks:  # pragma: no cover  # raised on super
            raise ValueError(
                "Tasks client is not configured. Call `configure()` first."
            )

    def list_tasks(
        self,
        params: TaskItemsRequest | Dict[str, Any] | None = None,
    ) -> TaskItemsResponse:
        """List tasks synchronously.

        Parameters
        ----------
        params : TaskItemsRequest | Dict[str, Any] | None, optional
            The query parameters for pagination, by default None
            (see TaskItemsRequest for details)

        Returns
        -------
        TaskItemsResponse
            The response JSON
            (see TaskItemsResponse for details)

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        params_dict: Dict[str, Any] | None
        if params is None:
            params_dict = None
        elif isinstance(params, dict):
            params_dict = TaskItemsRequest.model_validate(params).model_dump(
                exclude_none=True
            )
        else:
            params_dict = params.model_dump(exclude_none=True)
        response = self.tasks.list_tasks(params_dict)  # type: ignore
        return TaskItemsResponse.model_validate(response)

    def create_task(
        self,
        task_data: TaskCreateRequest | Dict[str, Any],
    ) -> TaskResponse:
        """Trigger a new task synchronously.

        Parameters
        ----------
        task_data : TaskCreateRequest | Dict[str, Any]
            The task data

        Returns
        -------
        TaskResponse
            The response JSON
            (see TaskResponse for details)

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        if isinstance(task_data, dict):
            task_data = TaskCreateRequest.model_validate(task_data)
        file_data = task_data.file_data
        file_name = task_data.file_name
        input_timeout = task_data.input_timeout
        if isinstance(file_data, BytesIO):
            # If file_data is a BytesIO object, read its content
            file_data = file_data.getvalue()
        response = self.tasks.create_task(  # type: ignore
            file_data,
            file_name,
            input_timeout=input_timeout,
        )
        return TaskResponse.model_validate(response)

    def update_task(
        self,
        task_id: str,
        task_data: TaskUpdateRequest | Dict[str, Any],
    ) -> TaskResponse:
        """Update a task synchronously.

        Parameters
        ----------
        task_id : str
            The task ID
        task_data : TaskUpdateRequest | Dict[str, Any]
            The task data

        Returns
        -------
        TaskResponse
            The response JSON

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        if isinstance(task_data, dict):
            task_data = TaskUpdateRequest.model_validate(task_data)
        task_dict = task_data.model_dump()
        response = self.tasks.update_task(task_id, task_dict)  # type: ignore
        return TaskResponse.model_validate(response)

    def get_task(self, task_id: str) -> TaskResponse:
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
        response = self.tasks.get_task(task_id)  # type: ignore
        return TaskResponse.model_validate(response)

    def send_user_input(
        self,
        request_data: UserInputRequest | Dict[str, Any],
        use_rest: bool = False,
    ) -> None:
        """Send user input to a task synchronously.

        Parameters
        ----------
        request_data : UserInputRequest | Dict[str, Any]
            The user input request data
        use_rest : bool, optional
            Whether to use REST API instead of first trying WebSocket,
            by default False

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        if isinstance(request_data, dict):
            request_data = UserInputRequest.model_validate(request_data)
        task_id = request_data.task_id
        user_input = request_data.data
        request_id = request_data.request_id
        sent = False
        if use_rest is False:  # pragma: no branch
            # first check/try using websockets
            if self.ws_sync and self.ws_sync.is_listening():
                message = {
                    "data": user_input,
                    "request_id": request_id,
                }
                # pylint: disable=broad-exception-caught
                try:
                    self.ws_sync.send(task_id, json.dumps(message))
                    sent = True
                except BaseException as e:  # pragma: no cover
                    self._handle_error(
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

    def cancel_task(self, task_id: str) -> TaskResponse:
        """Cancel a task synchronously.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        TaskResponse
            The response JSON

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        response = self.tasks.cancel_task(task_id)  # type: ignore
        return TaskResponse.model_validate(response)

    def delete_task(self, task_id: str, force: bool = False) -> None:
        """Delete a task synchronously.

        Parameters
        ----------
        task_id : str
            The task ID
        force : bool, optional
            Whether to force delete the task (even if active), by default False

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        self.tasks.delete_task(task_id, force=force)  # type: ignore

    def delete_tasks(
        self,
        ids: List[str] | None = None,
        force: bool = False,
    ) -> None:
        """Delete multiple tasks synchronously.

        Parameters
        ----------
        ids : List[str] | None, optional
            The list of task IDs to delete, by default None
        force : bool, optional
            Whether to force delete the tasks (even if active), by default False

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        self.tasks.delete_tasks(ids=ids, force=force)  # type: ignore

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

    def stop_ws_listener(self) -> None:
        """Stop the WebSocket listener (sync)."""
        if self.ws_sync:  # pragma: no branch
            self.ws_sync.stop()
            self.ws_sync = None

    async def a_list_tasks(
        self,
        params: TaskItemsRequest | Dict[str, Any] | None = None,
    ) -> TaskItemsResponse:
        """List tasks asynchronously.

        Parameters
        ----------
        params : TaskItemsRequest | Dict[str, Any] | None, optional
            The query parameters for pagination, by default None
            (see TaskItemsRequest for details)
        Returns
        -------
        TaskItemsResponse
            The (paginated) task items response

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        params_dict: Dict[str, Any] | None
        if params is None:
            params_dict = None
        elif isinstance(params, dict):
            params_dict = TaskItemsRequest.model_validate(params).model_dump(
                exclude_none=True
            )
        else:
            params_dict = params.model_dump(exclude_none=True)
        response = await self.tasks.a_list_tasks(params_dict)  # type: ignore
        return TaskItemsResponse.model_validate(response)

    async def a_create_task(
        self,
        task_data: TaskCreateRequest | Dict[str, Any],
    ) -> TaskResponse:
        """Trigger a new task asynchronously.

        Parameters
        ----------
        task_data : TaskCreateRequest | Dict[str, Any]
            The task data
            (see TaskCreateRequest for details)

        Returns
        -------
        TaskResponse
            The response JSON
            (see TaskResponse for details)

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        if isinstance(task_data, dict):
            task_data = TaskCreateRequest.model_validate(task_data)
        file_data = task_data.file_data
        file_name = task_data.file_name
        input_timeout = task_data.input_timeout
        response = await self.tasks.a_create_task(  # type: ignore
            file_data,
            file_name,
            input_timeout=input_timeout,
        )
        return TaskResponse.model_validate(response)

    async def a_get_task(self, task_id: str) -> TaskResponse:
        """Retrieve the status of a task asynchronously.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        TaskResponse
            The response JSON
            (see TaskResponse for details)

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        response = await self.tasks.a_get_task(task_id)  # type: ignore
        return TaskResponse.model_validate(response)

    async def a_update_task(
        self,
        task_id: str,
        task_data: TaskUpdateRequest | Dict[str, Any],
    ) -> TaskResponse:
        """Update a task asynchronously.

        Parameters
        ----------
        task_id : str
            The task ID
        task_data : TaskUpdateRequest | Dict[str, Any]
            The task data

        Returns
        -------
        TaskResponse
            The response JSON

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        if isinstance(task_data, dict):
            task_data = TaskUpdateRequest.model_validate(task_data)
        task_dict = task_data.model_dump()
        response = await self.tasks.a_update_task(  # type: ignore
            task_id,
            task_dict,
        )
        return TaskResponse.model_validate(response)

    async def a_send_user_input(
        self,
        request_data: UserInputRequest | Dict[str, Any],
        use_rest: bool = False,
    ) -> None:
        """Send user input to a task asynchronously.

        Parameters
        ----------
        request_data : UserInputRequest | Dict[str, Any]
            The user input request data
        use_rest : bool, optional
            Whether to use REST API instead of first trying WebSocket,
            by default False

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        if isinstance(request_data, dict):
            request_data = UserInputRequest.model_validate(request_data)
        task_id = request_data.task_id
        user_input = request_data.data
        request_id = request_data.request_id
        sent = False
        if use_rest is False:  # pragma: no branch
            # first check/try using websockets
            if self.ws_async and self.ws_async.is_listening():
                # pylint: disable=broad-exception-caught
                try:
                    message = {
                        "data": user_input,
                        "request_id": request_id,
                    }
                    await self.ws_async.send(task_id, json.dumps(message))
                    sent = True
                except BaseException as e:  # pragma: no cover
                    self._handle_error(
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

    async def a_cancel_task(self, task_id: str) -> TaskResponse:
        """Cancel or delete a task asynchronously.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        TaskResponse
            The response JSON
            (see TaskResponse for details)

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        response = await self.tasks.a_cancel_task(task_id)  # type: ignore
        return TaskResponse.model_validate(response)

    async def a_delete_task(self, task_id: str, force: bool = False) -> None:
        """Delete a task asynchronously.

        Parameters
        ----------
        task_id : str
            The task ID
        force : bool, optional
            Whether to force delete the task (even if active), by default False

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        await self.tasks.a_delete_task(task_id, force=force)  # type: ignore

    async def a_delete_tasks(
        self,
        ids: List[str] | None = None,
        force: bool = False,
    ) -> None:
        """Delete all tasks asynchronously.

        Parameters
        ----------
        ids : List[str] | None, optional
            The list of task IDs to delete, by default None
            If None, all tasks will be deleted.
        force : bool, optional
            Whether to force delete the tasks (even if active), by default False

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        await self.tasks.a_delete_tasks(ids=ids, force=force)  # type: ignore

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

    async def stop_ws_async_listener(self) -> None:
        """Stop the WebSocket listener (async)."""
        if self.ws_async:  # pragma: no branch
            await self.ws_async.stop()
            self.ws_async = None
