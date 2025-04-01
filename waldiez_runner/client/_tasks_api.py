# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
#
# flake8: noqa: E501
# pylint: disable=line-too-long
"""Tasks API client implementation."""

import asyncio
import inspect
from typing import Any, Callable, Coroutine, Dict

import httpx

from ._auth import CustomAuth


class TasksAPIClient:
    """Tasks API client."""

    url_prefix = "/api/v1/tasks"

    def __init__(
        self,
        auth: CustomAuth | None,
        on_error: (
            Callable[[str], None]
            | Callable[[str], Coroutine[Any, Any, None]]
            | None
        ) = None,
    ) -> None:
        """Initialize the client.

        Parameters
        ----------
        auth : CustomAuth
            The authentication instance
        on_error : Callable[[str], None] | Callable[[str], Coroutine[Any, Any, None]] | None
            The error handler
        """
        self._auth = auth
        self.on_error = on_error
        if auth:
            self.configure(auth)

    def configure(self, auth: CustomAuth) -> None:
        """Configure the client.

        Parameters
        ----------
        auth : CustomAuth
            The authentication instance

        Raises
        ------
        ValueError
            If the base URL is not set
        """
        self._auth = auth
        if not auth.base_url:
            raise ValueError("Base URL is required")
        if not self.on_error and auth.on_error:
            self.on_error = auth.on_error

    def _ensure_configured(self) -> None:
        """Ensure the client is configured.

        Raises
        ------
        ValueError
            If the client is not configured
        """
        if not self._auth or not self._auth.base_url:
            raise ValueError("Client is not configured")

    def trigger_task(self, file_data: bytes, file_name: str) -> Dict[str, Any]:
        """Trigger a task.
        Parameters
        ----------
        file_data : bytes
            The file data
        file_name : str
            The file name

        Returns
        -------
        Dict[str, Any]
            The response JSON

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self._ensure_configured()
        files = {"file": (file_name, file_data)}
        url = self.url_prefix
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.post(url, files=files)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:
            self._handle_error(str(e))
            raise e
        return response.json()

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Retrieve the status of a task.

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
        httpx.HTTPError
            If the request fails
        """
        self._ensure_configured()
        url = f"{self.url_prefix}/{task_id}"
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:
            self._handle_error(str(e))
            raise e
        return response.json()

    def download_task_results(self, task_id: str) -> bytes:
        """Download a completed task's results archive.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        BytesIO
            The results archive

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self._ensure_configured()
        url = f"{self.url_prefix}/{task_id}/download"
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:
            self._handle_error(str(e))
            raise e
        return response.content

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel or delete a task.

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
        httpx.HTTPError
            If the request fails
        """
        self._ensure_configured()
        url = f"{self.url_prefix}/{task_id}"
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.delete(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:
            self._handle_error(str(e))
            raise e
        return response.json()

    async def a_trigger_task(
        self, file_data: bytes, file_name: str
    ) -> Dict[str, Any]:
        """Trigger a task asynchronously.

        Parameters
        ----------
        file_data : bytes
            The file data
        file_name : str
            The file name

        Returns
        -------
        Dict[str, Any]
            The response JSON

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self._ensure_configured()
        files = {"file": (file_name, file_data)}
        url = self.url_prefix
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.post(url, files=files)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:
            self._handle_error(str(e))
            raise e
        return response.json()

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
        httpx.HTTPError
            If the request fails
        """
        self._ensure_configured()
        url = f"{self.url_prefix}/{task_id}"
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:
            self._handle_error(str(e))
            raise e
        return response.json()

    async def a_download_task_results(self, task_id: str) -> bytes:
        """Download a completed task's results archive asynchronously.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        BytesIO
            The results archive

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self._ensure_configured()
        url = f"{self.url_prefix}/{task_id}/download"
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:
            self._handle_error(str(e))
            raise e
        return response.content

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
        httpx.HTTPError
            If the request fails
        """
        self._ensure_configured()
        url = f"{self.url_prefix}/{task_id}"
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.delete(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:
            self._handle_error(str(e))
            raise e
        return response.json()

    def _handle_error(self, message: str) -> None:
        """Handle errors using the provided callback (sync or async).

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
                except RuntimeError:  # pragma: no branch
                    asyncio.run(self.on_error(message))
            else:
                self.on_error(message)
