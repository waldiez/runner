# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
#
# flake8: noqa: E501
# pylint: disable=line-too-long,broad-exception-caught,too-many-try-statements
"""Waldiez serve WebSocket clients."""

import asyncio
import logging
import threading
import time
from typing import Any, Callable, Coroutine, Dict

import websockets.asyncio.client
import websockets.sync.client
from websockets.exceptions import ConnectionClosed, InvalidStatus

from ._auth import CustomAuth

LOG = logging.getLogger(__name__)


class SyncWebSocketClient:
    """Synchronous WebSocket client with authentication and optional threading."""

    def __init__(
        self,
        auth: CustomAuth,
        reconnect: bool = True,
        max_retries: int = 5,
    ) -> None:
        """Initialize the synchronous WebSocket client."""
        self.auth = auth
        self.reconnect = reconnect
        self.max_retries = max_retries
        self.stop_event = threading.Event()
        self.ws_url = (
            auth.base_url.replace("http", "ws") + "/ws"
            if auth.base_url
            else "/ws"
        )
        self.listener_thread: threading.Thread | None = None

    def _get_headers(self) -> Dict[str, str]:
        """Get the headers to use for the WebSocket connection."""
        return {"Authorization": f"Bearer {self.auth.sync_get_token()}"}

    def is_listening(self) -> bool:
        """Check if the WebSocket listener is running.

        Returns
        -------
        bool
            True if the listener is running, False otherwise
        """
        if self.listener_thread is not None and self.listener_thread.is_alive():
            return True
        return not self.stop_event.is_set()

    def listen(
        self,
        task_id: str,
        on_message: Callable[[str], None],
        on_error: Callable[[str], None] | None = None,
        in_thread: bool = True,
    ) -> None:
        """Start listening to the WebSocket and store messages in the queue.

        If `in_thread` is True, runs in a separate thread.

        Parameters
        ----------
        task_id : str
            The task ID to use for the WebSocket connection
        on_message : Callable[[str], None]
            The function to call when a message is received
        on_error : Callable[[str], None], optional
            The function to call on error, by default None
        in_thread : bool, optional
            Whether to run the listener in a separate thread, by default True
        """
        if self.is_listening():
            return
        self.stop_event.clear()
        if not in_thread:
            self._listen(task_id, on_message, on_error)
        else:
            self.listener_thread = threading.Thread(
                target=self._listen,
                args=(task_id, on_message, on_error),
                daemon=True,
            )
            self.listener_thread.start()

    # pylint: disable=too-complex,too-many-branches
    # maybe refactor this method to reduce complexity
    def _listen(
        self,
        task_id: str,
        on_message: Callable[[str], None],
        on_error: Callable[[str], None] | None,
    ) -> None:
        """Internal method to listen for messages and store them in the queue."""
        retries = 0
        while not self.stop_event.is_set():
            try:
                additional_headers = self._get_headers()
                with websockets.sync.client.connect(
                    f"{self.ws_url}/{task_id}",
                    additional_headers=additional_headers,
                ) as websocket:
                    retries = 0
                    while not self.stop_event.is_set():
                        try:
                            message = websocket.recv(timeout=1, decode=True)
                            message_str = (
                                str(message)
                                if not isinstance(message, str)
                                else message
                            )
                            on_message(message_str)
                        except ConnectionClosed:
                            break
                        except TimeoutError:
                            pass
                        except BaseException as e:
                            LOG.error("WebSocket Error (sync): %s", e)
            except InvalidStatus as e:
                status_code = e.response.status_code
                if status_code == 404:
                    LOG.error(
                        "WebSocket task not found, please check the task ID."
                    )
                    if on_error:
                        on_error(str(e))
                    self.stop_event.set()
                    break
                if status_code == 400:
                    # bad request: either too-many-clients or too-many-tasks for client
                    LOG.error("Too many clients or tasks for task %s", task_id)
                    if on_error:
                        on_error(str(e))
                    self.stop_event.set()
                    break
                if status_code in (401, 403):
                    LOG.warning(
                        "Could not connect to WebSocket, refreshing token..."
                    )
                    LOG.warning(e.response.reason_phrase)
                    LOG.warning(e.response)
                    # self.auth.sync_get_token(force=True)
                    continue
            except BaseException as e:
                retries += 1
                if not self.reconnect or retries >= self.max_retries:
                    if on_error:
                        on_error(str(e))
                    break
                time.sleep(min(2**retries, 30))

    def send(self, task_id: str, message: str) -> None:
        """Send a message to the WebSocket server.

        Parameters
        ----------
        task_id : str
            The task ID to use for the WebSocket connection
        message : str
            The message to send
        """

        def send_func() -> None:
            headers = self._get_headers()
            try:
                with websockets.sync.client.connect(
                    f"{self.ws_url}/{task_id}", additional_headers=headers
                ) as websocket:
                    websocket.send(message)
            except BaseException as e:  # pylint: disable=broad-exception-caught
                LOG.error("WebSocket Error (sync): %s", e)

        threading.Thread(target=send_func, daemon=True).start()

    def stop(self) -> None:
        """Stop the WebSocket listener."""
        self.stop_event.set()
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2)
        self.listener_thread = None


class AsyncWebSocketClient:
    """Asynchronous WebSocket client with authentication and reconnect handling."""

    def __init__(
        self,
        auth: CustomAuth,
        reconnect: bool = True,
        max_retries: int = 5,
    ) -> None:
        """Initialize the async WebSocket client."""
        self.auth = auth
        self.reconnect = reconnect
        self.max_retries = max_retries
        self.stop_event = asyncio.Event()
        self.ws_url = (
            auth.base_url.replace("http", "ws") + "/ws"
            if auth.base_url
            else "/ws"
        )
        self.listener_task: asyncio.Task[Any] | None = None

    async def _get_headers(self) -> Dict[str, str]:
        """Get the headers to use for the WebSocket connection."""
        return {"Authorization": f"Bearer {await self.auth.async_get_token()}"}

    async def listen(
        self,
        task_id: str,
        on_message: Callable[[str], Coroutine[Any, Any, None]],
        on_error: Callable[[str], Coroutine[Any, Any, None]] | None = None,
        in_task: bool = True,
    ) -> None:
        """Start listening to the WebSocket and store messages in the async queue.

        Parameters
        ----------
        task_id : str
            The task ID to listen to
        on_message : Callable[[str], Coroutine[Any, Any, None]]
            The function to call when a message is received
        on_error : Callable[[str], Coroutine[Any, Any, None]], optional
            The function to call on error, by default None
        in_task : bool, optional
            Whether to run the listener in a separate task, by default True
        """
        if await self.is_listening():
            return
        self.stop_event.clear()
        if not in_task:
            await self._listen(task_id, on_message, on_error)
        else:
            self.listener_task = asyncio.create_task(
                self._listen(task_id, on_message, on_error)
            )

    async def is_listening(self) -> bool:
        """Check if the WebSocket listener is running.

        Returns
        -------
        bool
            True if the listener is running, False otherwise
        """
        if self.listener_task is not None and not self.listener_task.done():
            return True
        return not self.stop_event.is_set()

    # pylint: disable=too-complex
    async def _listen(
        self,
        task_id: str,
        on_message: Callable[[str], Coroutine[Any, Any, None]],
        on_error: Callable[[str], Coroutine[Any, Any, None]] | None,
    ) -> None:
        """Internal async method to listen for messages."""
        retries = 0
        while not self.stop_event.is_set():
            try:
                async with websockets.asyncio.client.connect(
                    f"{self.ws_url}/{task_id}",
                    extra_headers=self._get_headers(),
                ) as websocket:
                    retries = 0
                    while not self.stop_event.is_set():
                        try:
                            message = await asyncio.wait_for(
                                websocket.recv(), timeout=1
                            )
                            if message:
                                message_str = (
                                    str(message)
                                    if not isinstance(message, str)
                                    else message
                                )
                                await on_message(message_str)
                        except ConnectionClosed:
                            break
                        except asyncio.TimeoutError:
                            pass
                        except BaseException as e:
                            LOG.error("WebSocket Error (async): %s", e)
            except InvalidStatus as e:
                if e.response.status_code in (401, 403):
                    LOG.warning("Invalid token detected, refreshing token...")
                    await self.auth.async_get_token(force=True)
                    continue
                LOG.error("WebSocket Error (async): %s", e)
            except BaseException as e:
                LOG.error("WebSocket Error (async): %s", e)
                retries += 1
                if not self.reconnect or retries >= self.max_retries:
                    if on_error:
                        await on_error(str(e))
                    break
                await asyncio.sleep(min(2**retries, 30))

    async def send(self, task_id: str, message: str) -> None:
        """Send a message to the WebSocket server.

        Parameters
        ----------
        task_id : str
            The task ID to send the message to
        message : str
            The message to send
        """
        try:
            extra_headers = await self._get_headers()
            async with websockets.asyncio.client.connect(
                f"{self.ws_url}/{task_id}", extra_headers=extra_headers
            ) as websocket:
                await websocket.send(message)
        except BaseException as e:
            LOG.error("WebSocket Error (async): %s", e)

    async def stop(self) -> None:
        """Stop the async WebSocket listener."""
        self.stop_event.set()
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await asyncio.wait_for(self.listener_task, timeout=2)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                pass
            finally:
                self.listener_task = None
