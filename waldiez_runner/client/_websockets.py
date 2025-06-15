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

from .auth import Auth

LOG = logging.getLogger(__name__)


class SyncWebSocketClient:
    """Synchronous WebSocket client with authentication and optional threading."""

    def __init__(
        self,
        auth: Auth,
        reconnect: bool = True,
        max_retries: int = 5,
    ) -> None:
        """Initialize the synchronous WebSocket client.

        Parameters
        ----------
        auth : CustomAuth
            The authentication object
        reconnect : bool, optional
            Whether to reconnect on error, by default True
        max_retries : int, optional
            The maximum number of retries on error, by default 5
        """
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
        """Get the headers to use for the WebSocket connection.

        Returns
        -------
        Dict[str, str]
            The headers to use for the WebSocket connection
        """
        return {"Authorization": f"Bearer {self.auth.sync_get_token()}"}

    def is_listening(self) -> bool:
        """Check if the WebSocket listener is running.
        Returns
        -------
        bool
            True if the listener is running, False otherwise
        """
        return (
            self.listener_thread is not None and self.listener_thread.is_alive()
        )

    def listen(
        self,
        task_id: str,
        on_message: Callable[[str], None],
        on_error: Callable[[str], None] | None = None,
        in_thread: bool = True,
    ) -> None:
        """Start listening to the WebSocket and store messages in the queue.

        Parameters
        ----------
        task_id : str
            The task ID to listen to
        on_message : Callable[[str], None]
            The function to call when a message is received
        on_error : Callable[[str], None] | None, optional
            The function to call on error, by default None
        in_thread : bool, optional
            Whether to run the listener in a separate thread, by default True
        """
        if in_thread and self.is_listening():
            return
        self.stop_event.clear()
        if in_thread:
            self.listener_thread = threading.Thread(
                target=self._listen,
                args=(task_id, on_message, on_error),
                daemon=True,
            )
            self.listener_thread.start()
        else:
            self._listen(task_id, on_message, on_error)

    def _listen(
        self,
        task_id: str,
        on_message: Callable[[str], None],
        on_error: Callable[[str], None] | None,
    ) -> None:
        """Internal method to listen for messages.

        Parameters
        ----------
        task_id : str
            The task ID to listen to
        on_message : Callable[[str], None]
            The function to call when a message is received
        on_error : Callable[[str], None] | None
            The function to call on error
        """
        retries = 0
        while not self.stop_event.is_set():
            try:
                self._connect_and_receive(task_id, on_message)
                retries = 0  # Reset after success
            except InvalidStatus as e:
                if self._handle_status_error(e, task_id, on_error):
                    self.stop_event.set()
            except BaseException as e:
                retries += 1
                if not self.reconnect or retries > self.max_retries:
                    if on_error:  # pragma: no branch
                        on_error(str(e))
                    self.stop_event.set()
                if not self.stop_event.is_set():
                    delay = exponential_backoff(retries)
                    LOG.warning(
                        "WebSocket Error (sync): %s, reconnecting in %d seconds...",
                        e,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    LOG.warning("Stopping listener due to stop event.")
                    break
        self.stop_event.set()

    def _connect_and_receive(
        self,
        task_id: str,
        on_message: Callable[[str], None],
    ) -> None:
        """Connect to the WebSocket server and receive messages.

        Parameters
        ----------
        task_id : str
            The task ID to listen to
        on_message : Callable[[str], None]
            The function to call when a message is received
        """
        headers = self._get_headers()
        with websockets.sync.client.connect(
            f"{self.ws_url}/{task_id}",
            additional_headers=headers,
        ) as websocket:
            while not self.stop_event.is_set():
                try:
                    message = websocket.recv(timeout=1, decode=True)
                    message_str = ensure_str(message)
                    on_message(message_str)
                except ConnectionClosed:  # pragma: no cover
                    LOG.debug("Connection closed, stopping listener.")
                    break
                except TimeoutError:  # pragma: no cover
                    continue
                except BaseException as e:  # pragma: no cover
                    LOG.error("Ws error on connect and rcv (sync): %s", e)
                    break

    def _handle_status_error(
        self,
        e: InvalidStatus,
        task_id: str,
        on_error: Callable[[str], None] | None,
    ) -> bool:
        """Handle specific status errors.

        Parameters
        ----------
        e : InvalidStatus
            The exception raised
        task_id : str
            The task ID that caused the error
        on_error : Callable[[str], None] | None
            The function to call on error
        Returns
        -------
        bool
            True if the listener should stop, False otherwise
        """
        code: int | None = getattr(e.response, "status_code", None)  # fallback

        if hasattr(e, "code"):  # pragma: no cover
            try:
                code = int(e.code)  # pyright: ignore
            except ValueError:
                pass

        if code == 1008:  # Policy Violation # pragma: no cover
            LOG.warning("Unauthorized (1008): Token likely invalid.")
            self.auth.sync_get_token(force=True)
            return False

        if code == 1003:  # Unsupported data # pragma: no cover
            LOG.error("Unsupported data type for task %s", task_id)
            if on_error:
                on_error(str(e))
            return True

        if code == 1000:  # pragma: no cover
            LOG.info("Normal closure from server.")
            return True

        if on_error:  # pragma: no branch
            on_error(str(e))
        return True

    def send(self, task_id: str, message: str) -> None:
        """Send a message to the WebSocket server.

        Parameters
        ----------
        task_id : str
            The task ID to send the message to
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
            except BaseException as e:  # pragma: no cover
                LOG.error("WebSocket Error (sync): %s", e)

        threading.Thread(target=send_func, daemon=True).start()

    def stop(self) -> None:
        """Stop the WebSocket listener."""
        self.stop_event.set()
        if (
            self.listener_thread and self.listener_thread.is_alive()
        ):  # pragma: no branch
            self.listener_thread.join(timeout=2)
        self.listener_thread = None


class AsyncWebSocketClient:
    """Asynchronous WebSocket client with authentication and reconnect handling."""

    def __init__(
        self,
        auth: Auth,
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
        if self.is_listening():
            return
        self.stop_event.clear()
        if in_task:
            self.listener_task = asyncio.create_task(
                self._listen(task_id, on_message, on_error)
            )
        else:
            await self._listen(task_id, on_message, on_error)

    def is_listening(self) -> bool:
        """Check if the WebSocket listener is running.

        Returns
        -------
        bool
            True if the listener is running, False otherwise
        """
        return self.listener_task is not None and not self.listener_task.done()

    async def _listen(
        self,
        task_id: str,
        on_message: Callable[[str], Coroutine[Any, Any, None]],
        on_error: Callable[[str], Coroutine[Any, Any, None]] | None,
    ) -> None:
        """Internal method to listen for messages.

        Parameters
        ----------
        task_id : str
            The task ID to listen to
        on_message : Callable[[str], Coroutine[Any, Any, None]]
            The function to call when a message is received
        on_error : Callable[[str], Coroutine[Any, Any, None]] | None
            The function to call on error
        """
        retries = 0
        try:
            while not self.stop_event.is_set():
                try:
                    await self._connect_and_receive(task_id, on_message)
                    retries = 0  # reset on success
                except InvalidStatus as e:
                    if await self._handle_status_error(e, task_id, on_error):
                        break
                except BaseException as e:
                    LOG.error("WebSocket Error (async): %s", e)
                    retries += 1
                    if not self.reconnect or retries > self.max_retries:
                        if on_error:  # pragma: no branch
                            await on_error(str(e))
                        break
                    if not self.stop_event.is_set():
                        delay = exponential_backoff(retries)
                        LOG.warning("Reconnecting in %d seconds...", delay)
                        await asyncio.sleep(delay)
                    else:  # pragma: no cover
                        break
        finally:
            self.stop_event.set()

    async def _connect_and_receive(
        self,
        task_id: str,
        on_message: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        """Connect to the WebSocket server and receive messages.

        Parameters
        ----------
        task_id : str
            The task ID to listen to
        on_message : Callable[[str], Coroutine[Any, Any, None]]
            The function to call when a message is received
        """
        headers = await self._get_headers()
        async with websockets.asyncio.client.connect(
            f"{self.ws_url}/{task_id}",
            extra_headers=headers,
        ) as websocket:
            while not self.stop_event.is_set():  # pragma: no branch
                try:
                    message = await asyncio.wait_for(
                        websocket.recv(), timeout=1
                    )
                    if message:  # pragma: no branch
                        await on_message(ensure_str(message))
                except ConnectionClosed:
                    self.stop_event.set()
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:  # pragma: no cover
                    self.stop_event.set()
                except BaseException as e:
                    LOG.error("WebSocket Error (recv async): %s", e)
                    self.stop_event.set()

    async def _handle_status_error(
        self,
        e: InvalidStatus,
        task_id: str,
        on_error: Callable[[str], Coroutine[Any, Any, None]] | None,
    ) -> bool:
        """Handle specific status errors.

        Parameters
        ----------
        e : InvalidStatus
            The exception raised
        task_id : str
            The task ID that caused the error
        on_error : Callable[[str], Coroutine[Any, Any, None]] | None
            The function to call on error
        Returns
        -------
        bool
            True if the listener should stop, False otherwise
        """
        code = getattr(e, "code", None) or getattr(
            e.response, "status_code", None
        )

        if code == 1008:
            LOG.warning("Unauthorized (1008): refreshing token...")
            await self.auth.async_get_token(force=True)
            return False
        if code == 1000:  # pragma: no cover
            LOG.info("Normal closure for task %s", task_id)
            return True
        if on_error:  # pragma: no branch
            await on_error(str(e))
        return True

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
            headers = await self._get_headers()
            async with websockets.asyncio.client.connect(
                f"{self.ws_url}/{task_id}", extra_headers=headers
            ) as websocket:
                await websocket.send(message)
        except BaseException as e:  # pragma: no cover
            LOG.error("WebSocket Error (async send): %s", e)

    async def stop(self) -> None:
        """Stop the WebSocket listener."""
        self.stop_event.set()
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await asyncio.wait_for(self.listener_task, timeout=1)
            except (
                asyncio.TimeoutError,
                asyncio.CancelledError,
            ):  # pragma: no cover
                pass
            self.listener_task = None


def exponential_backoff(retries: int) -> float:
    """Calculate the exponential backoff time.
    Parameters
    ----------
    retries : int
        The number of retries
    Returns
    -------
    float
        The backoff time in seconds
    """
    return min(2**retries, 30)


def ensure_str(msg: str | bytes) -> str:
    """Ensure the message is a string.

    Parameters
    ----------
    msg : str | bytes
        The message to format
    Returns
    -------
    str
        The formatted message
    """
    return str(msg) if not isinstance(msg, str) else msg
