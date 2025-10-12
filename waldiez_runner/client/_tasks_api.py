# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pyright: reportArgumentType=false,reportOptionalMemberAccess=false

"""Tasks API client implementation."""

from typing import Any

import httpx

from ._api_base import BaseAPIClient


# noinspection DuplicatedCode
class TasksAPIClient(BaseAPIClient):
    """Tasks API client."""

    url_prefix = "/api/v1/tasks"

    def list_tasks(
        self, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """List all tasks.

        Parameters
        ----------
        params : dict[str, Any] | None
            The query parameters to filter the tasks
            like for pagination, status, etc.
            (default: None)

        Returns
        -------
        Dict[str, Any]
            The response JSON

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.get(self.url_prefix, params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
        return response.json()

    def create_task(
        self, file_data: bytes, file_name: str, input_timeout: int = 180
    ) -> dict[str, Any]:
        """Trigger a task.
        Parameters
        ----------
        file_data : bytes
            The file data
        file_name : str
            The file name
        input_timeout : int
            The input timeout in seconds (default: 180)

        Returns
        -------
        dict[str, Any]
            The response JSON

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        files = {"file": (file_name, file_data)}
        url = f"{self.url_prefix}?input_timeout={input_timeout}"
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.post(url, files=files)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
        return response.json()

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Retrieve the status of a task.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        dict[str, Any]
            The response JSON

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        url = f"{self.url_prefix}/{task_id}"
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
        return response.json()

    def update_task(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a task.

        Parameters
        ----------
        task_id : str
            The task ID
        data : dict[str, Any]
            The data to update

        Returns
        -------
        dict[str, Any]
            The response JSON

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        url = f"{self.url_prefix}/{task_id}"
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.put(url, json=data)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
        return response.json()

    def send_user_input(
        self,
        task_id: str,
        user_input: str,
        request_id: str,
    ) -> None:
        """Send user input to a task.

        Parameters
        ----------
        task_id : str
            The task ID
        user_input : str
            The user input
        request_id : str
            The request ID

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        url = f"{self.url_prefix}/{task_id}/input"
        data = {"data": user_input, "request_id": request_id}
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.post(url, json=data)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

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
        self.ensure_configured()
        url = f"{self.url_prefix}/{task_id}/download"
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
        return response.content

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        """Cancel or delete a task.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        dict[str, Any]
            The response JSON

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        url = f"{self.url_prefix}/{task_id}/cancel"
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.post(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
        return response.json()

    def delete_task(self, task_id: str, force: bool = False) -> None:
        """Delete a task.

        Parameters
        ----------
        task_id : str
            The task ID
        force : bool
            Whether to force delete the task (even if active, default: False)

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        url = f"{self.url_prefix}/{task_id}"
        if force:
            url += "?force=true"
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.delete(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    def delete_tasks(
        self, ids: list[str] | None = None, force: bool = False
    ) -> None:
        """Delete all tasks for the client.

        Parameters
        ----------
        ids : list[str] | None
            The task IDs to delete (default: None)
            If None, all tasks will be deleted.
        force : bool
            Whether to force delete the tasks (even if active, default: False)

        Raises
        ------
        httpx.HTTPError
            If the request fails
        httpx.HTTPStatusError
            If the request fails with a 4xx or 5xx status code
        ValueError
            If the client is not configured
        """
        self.ensure_configured()
        force_str = "true" if force else "false"
        query_params = f"?force={force_str}"
        if ids:
            for task_id in ids:
                query_params += f"&ids={task_id}"
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.delete(f"{self.url_prefix}{query_params}")
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    async def a_list_tasks(
        self, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """List all tasks asynchronously.

        Parameters
        ----------
        params : dict[str, Any] | None
            The query parameters to filter the tasks
            like for pagination, status, etc.
            (default: None)

        Returns
        -------
        dict[str, Any]
            The response JSON

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        # pylint: disable=duplicate-code
        # also in ./clients_api.py
        self.ensure_configured()
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.get(self.url_prefix, params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
        return response.json()

    async def a_create_task(
        self,
        file_data: bytes,
        file_name: str,
        input_timeout: int = 180,
    ) -> dict[str, Any]:
        """Trigger a task asynchronously.

        Parameters
        ----------
        file_data : bytes
            The file data
        file_name : str
            The file name
        input_timeout : int
            The input timeout in seconds (default: 180)

        Returns
        -------
        dict[str, Any]
            The response JSON

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        files = {"file": (file_name, file_data)}
        url = f"{self.url_prefix}?input_timeout={input_timeout}"
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.post(url, files=files)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
        return response.json()

    async def a_get_task(self, task_id: str) -> dict[str, Any]:
        """Retrieve the status of a task asynchronously.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        dict[str, Any]
            The response JSON

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        url = f"{self.url_prefix}/{task_id}"
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
        return response.json()

    async def a_update_task(
        self, task_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a task asynchronously.

        Parameters
        ----------
        task_id : str
            The task ID
        data : dict[str, Any]
            The data to update

        Returns
        -------
        dict[str, Any]
            The response JSON

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        url = f"{self.url_prefix}/{task_id}"
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.put(url, json=data)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:
            self.handle_error(str(e))
            raise e
        return response.json()

    async def a_send_user_input(
        self,
        task_id: str,
        user_input: str,
        request_id: str,
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

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        url = f"{self.url_prefix}/{task_id}/input"
        data = {"data": user_input, "request_id": request_id}
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.post(url, json=data)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

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
        self.ensure_configured()
        url = f"{self.url_prefix}/{task_id}/download"
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
        return response.content

    async def a_cancel_task(self, task_id: str) -> dict[str, Any]:
        """Cancel or delete a task asynchronously.

        Parameters
        ----------
        task_id : str
            The task ID

        Returns
        -------
        dict[str, Any]
            The response JSON

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        url = f"{self.url_prefix}/{task_id}/cancel"
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.post(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
        return response.json()

    async def a_delete_task(self, task_id: str, force: bool = False) -> None:
        """Delete a task asynchronously.

        Parameters
        ----------
        task_id : str
            The task ID
        force : bool
            Whether to force delete the task (even if active, default: False)

        Raises
        ------
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        url = f"{self.url_prefix}/{task_id}"
        if force:
            url += "?force=true"
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.delete(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    async def a_delete_tasks(
        self, ids: list[str] | None = None, force: bool = False
    ) -> None:
        """Delete all tasks for the client asynchronously.

        Parameters
        ----------
        ids : list[str] | None
            The task IDs to delete (default: None)
            If None, all tasks will be deleted.
        force : bool
            Whether to force delete the tasks (even if active, default: False)

        Raises
        ------
        httpx.HTTPError
            If the request fails
        httpx.HTTPStatusError
            If the request fails with a 4xx or 5xx status code
        ValueError
            If the client is not configured
        """
        self.ensure_configured()
        force_str = "true" if force else "false"
        query_params = f"?force={force_str}"
        if ids:
            for task_id in ids:
                query_params += f"&ids={task_id}"
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.delete(
                    f"{self.url_prefix}{query_params}",
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as e:  # pragma: no cover
            self.handle_error(e.response.text)
            raise e
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
