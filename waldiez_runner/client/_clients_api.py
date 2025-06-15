# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Clients API client implementation."""

from typing import Any, Dict, List

import httpx

from ._api_base import BaseAPIClient

# pylint: disable=too-many-try-statements


class ClientsAPIClient(BaseAPIClient):
    """Clients API client."""

    url_prefix = "/api/v1/clients"

    def list_clients(
        self, params: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Get all clients.

        Parameters
        ----------
        params : Dict[str, Any] | None
            The query parameters to filter the clients
            like for pagination, etc.
            If None, the server defaults will be used.
        Returns
        -------
        Dict[str, Any]
            The (paginated) list of clients ("items" key in the response)

        Raises
        ------
        ValueError
            If the client is not configured
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        # pylint: disable=too-many-try-statements
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.get(self.url_prefix, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    def get_client(self, client_id: str) -> Dict[str, Any]:
        """Get a client by ID.

        Parameters
        ----------
        client_id : str
            The client ID

        Returns
        -------
        Dict[str, Any]
            The client data

        Raises
        ------
        ValueError
            If the client is not configured
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.get(f"{self.url_prefix}/{client_id}")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    def create_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new client.

        Parameters
        ----------
        client_data : Dict[str, Any]
            The client data

        Returns
        -------
        Dict[str, Any]
            The created client data

        Raises
        ------
        ValueError
            If the client is not configured
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        # pylint: disable=too-many-try-statements
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.post(self.url_prefix, json=client_data)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    def update_client(
        self, client_id: str, update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a client.

        Parameters
        ----------
        client_id : str
            The client ID
        update_data : Dict[str, Any]
            The update data

        Returns
        -------
        Dict[str, Any]
            The updated client data

        Raises
        ------
        ValueError
            If the client is not configured
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.patch(
                    f"{self.url_prefix}/{client_id}", json=update_data
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    def delete_client(self, client_id: str) -> None:
        """Delete a client.

        Parameters
        ----------
        client_id : str
            The client ID

        Raises
        ------
        ValueError
            If the client is not configured
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.delete(f"{self.url_prefix}/{client_id}")
                response.raise_for_status()
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    def delete_clients(
        self,
        ids: List[str] | None = None,
        audiences: List[str] | None = None,
    ) -> None:
        """Delete clients by ids or audiences or all.

        Parameters
        ----------
        ids : List[str] | None
            The list of client IDs to delete
            If None, all clients will be deleted
        audiences : List[str] | None
            The list of audiences to delete clients for
            If None, all clients will be deleted

        Raises
        ------
        ValueError
            If the client is not configured
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        params: dict[str, list[str]] = {}
        if ids:
            params["ids"] = ids
        if audiences:
            params["audiences"] = audiences
        try:
            with httpx.Client(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = client.delete(self.url_prefix, params=params)
                response.raise_for_status()
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    async def a_list_clients(
        self, params: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Get all clients asynchronously.

        Parameters
        ----------
        params : Dict[str, Any] | None
            The query parameters to filter the clients
            like for pagination, etc.
            If None, the server defaults will be used.

        Returns
        -------
        Dict[str, Any]
            The (paginated) list of clients ("items" key in the response)

        Raises
        ------
        ValueError
            If the client is not configured
        httpx.HTTPError
            If the request fails
        """
        # pylint: disable=duplicate-code
        # also in ./tasks_api.py
        self.ensure_configured()
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.get(self.url_prefix, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    async def a_get_client(self, client_id: str) -> Dict[str, Any]:
        """Get a client by ID asynchronously.

        Parameters
        ----------
        client_id : str
            The client ID

        Returns
        -------
        Dict[str, Any]
            The client data

        Raises
        ------
        ValueError
            If the client is not configured
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.get(f"{self.url_prefix}/{client_id}")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    async def a_create_client(
        self, client_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new client asynchronously.

        Parameters
        ----------
        client_data : Dict[str, Any]
            The client data

        Returns
        -------
        Dict[str, Any]
            The created client data

        Raises
        ------
        ValueError
            If the client is not configured
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.post(self.url_prefix, json=client_data)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    async def a_update_client(
        self, client_id: str, update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a client asynchronously.

        Parameters
        ----------
        client_id : str
            The client ID
        update_data : Dict[str, Any]
            The update data

        Returns
        -------
        Dict[str, Any]
            The updated client data

        Raises
        ------
        ValueError
            If the client is not configured
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.patch(
                    f"{self.url_prefix}/{client_id}", json=update_data
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    async def a_delete_client(self, client_id: str) -> None:
        """Delete a client asynchronously.

        Parameters
        ----------
        client_id : str
            The client ID

        Raises
        ------
        ValueError
            If the client is not configured
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.delete(f"{self.url_prefix}/{client_id}")
                response.raise_for_status()
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e

    async def a_delete_clients(
        self,
        ids: List[str] | None = None,
        audiences: List[str] | None = None,
    ) -> None:
        """Delete clients by audience asynchronously.

        Parameters
        ----------
        ids : List[str] | None
            The list of client IDs to delete
            If None, all clients will be deleted
        audiences : List[str] | None
            The list of audiences to delete clients for
            If None, all clients will be deleted

        Raises
        ------
        ValueError
            If the client is not configured
        httpx.HTTPError
            If the request fails
        """
        self.ensure_configured()
        params: dict[str, list[str]] = {}
        if audiences:
            params["audiences"] = audiences
        if ids:
            params["ids"] = ids
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                base_url=self._auth.base_url,  # type: ignore
            ) as client:
                response = await client.delete(self.url_prefix, params=params)
                response.raise_for_status()
        except httpx.HTTPError as e:  # pragma: no cover
            self.handle_error(str(e))
            raise e
