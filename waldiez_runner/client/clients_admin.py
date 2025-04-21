# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Waldiez serve client admin."""

from typing import Any, Callable, Coroutine, Dict, List

from ._clients_api import ClientsAPIClient
from .client_base import BaseClient
from .models import (
    ClientAudience,
    ClientCreateRequest,
    ClientCreateResponse,
    ClientItemsRequest,
    ClientItemsResponse,
    ClientResponse,
)


class ClientsAdmin(BaseClient):
    """Client admin class.
    For interacting with /clients endpoints.

    Attributes
    ----------
    clients : ClientsAPIClient | None
        ClientsAPIClient instance for client management
    """

    clients: ClientsAPIClient | None = None

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
        """Initialize the client admin with optional late configuration."""
        self.clients = None
        super().__init__(
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
            on_auth_token=on_auth_token,
            on_auth_error=on_auth_error,
            on_error=on_error,
        )

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
        """Configure the authentication and Clients API client.

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
        if client_id and client_secret:  # pragma: no branch
            self.clients = ClientsAPIClient(
                auth=self.auth,
                on_error=self.on_error,
            )

    def list_clients(
        self,
        params: ClientItemsRequest | Dict[str, Any] | None = None,
    ) -> ClientItemsResponse:
        """Retrieve the list of clients synchronously.

        Parameters
        ----------
        params : ClientItemsRequest | Dict[str, Any] | None, optional
            The request (pagination) parameters, by default None
            If None, defaults to ClientItemsRequest with default values

        Returns
        -------
        CLientItemsResponse
            The paginated clients response ("items" key in JSON)
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
            params_dict = ClientItemsRequest.model_validate(params).model_dump(
                exclude_none=True
            )
        else:
            params_dict = params.model_dump(exclude_none=True)
        response = self.clients.list_clients(params=params_dict)  # type: ignore
        return ClientItemsResponse.model_validate(response)

    def get_client(self, client_id: str) -> ClientResponse:
        """Retrieve a specific client synchronously.

        Parameters
        ----------
        client_id : str
            The client ID

        Returns
        -------
        ClientResponse
            The client response

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        response = self.clients.get_client(client_id)  # type: ignore
        return ClientResponse.model_validate(response)

    def create_client(
        self,
        client_data: ClientCreateRequest | Dict[str, Any],
    ) -> ClientCreateResponse:
        """Create a new client synchronously.

        Parameters
        ----------
        client_data : ClientCreateRequest | Dict[str, Any]
            The client data

        Returns
        -------
        ClientCreateResponse
            The client create response

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        client_create: ClientCreateRequest = (
            client_data
            if not isinstance(client_data, dict)
            else ClientCreateRequest.model_validate(client_data)
        )
        response = self.clients.create_client(  # type: ignore
            client_data=client_create.model_dump(exclude_none=True),
        )
        return ClientCreateResponse.model_validate(response)

    def update_client(
        self,
        client_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> ClientResponse:
        """Update an existing client synchronously.

        Parameters
        ----------
        client_id : str
            The client ID
        name : str | None, optional
            The client name, by default None
        description : str | None, optional
            The client description, by default None

        Returns
        -------
        ClientResponse
            The client response

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        update_data = {
            "description": description,
        }
        if name:
            update_data["name"] = name
        response = self.clients.update_client(  # type: ignore
            client_id=client_id,
            update_data=update_data,
        )
        return ClientResponse.model_validate(response)

    def delete_client(self, client_id: str) -> None:
        """Delete a client synchronously.

        Parameters
        ----------
        client_id : str
            The client ID

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        self.clients.delete_client(client_id)  # type: ignore

    def delete_clients(
        self,
        ids: List[str] | None = None,
        audiences: List[ClientAudience] | None = None,
    ) -> None:
        """Delete multiple clients synchronously.

        Parameters
        ----------
        ids : List[str] | None, optional
            The client IDs to filter for deletion.
            If None, all clients will be deleted.
            (not the one used for this request)
        audiences : List[ClientAudience] | None, optional
            The audiences to filter for deletion.
            If None, all clients will be deleted.
            (not the one used for this request) )

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        self.clients.delete_clients(ids, audiences)  # type: ignore

    async def a_list_clients(self) -> ClientItemsResponse:
        """Retrieve the list of clients asynchronously.

        Returns
        -------
        ClientItemsResponse
            The paginated clients response ("items" key in JSON)

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        response = await self.clients.a_list_clients()  # type: ignore
        return ClientItemsResponse.model_validate(response)

    async def a_get_client(self, client_id: str) -> ClientResponse:
        """Retrieve a specific client asynchronously.

        Parameters
        ----------
        client_id : str
            The client ID

        Returns
        -------
        ClientResponse
            The client response

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        response = await self.clients.a_get_client(client_id)  # type: ignore
        return ClientResponse.model_validate(response)

    async def a_create_client(
        self,
        client_data: ClientCreateRequest | Dict[str, Any],
    ) -> ClientCreateResponse:
        """Create a new client asynchronously.

        Parameters
        ----------
        client_data : Dict[str, Any]
            The client data

        Returns
        -------
        ClientCreateResponse
            The client create response

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        client_create: ClientCreateRequest = (
            client_data
            if not isinstance(client_data, dict)
            else ClientCreateRequest.model_validate(client_data)
        )
        response = await self.clients.a_create_client(  # type: ignore
            client_data=client_create.model_dump(exclude_none=True),
        )
        return ClientCreateResponse.model_validate(response)

    async def a_update_client(
        self,
        client_id: str,
        description: str | None = None,
    ) -> ClientResponse:
        """Update an existing client asynchronously.

        Parameters
        ----------
        client_id : str
            The client ID
        description : str | None, optional
            The client description, by default None

        Returns
        -------
        ClientResponse
            The client response

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        update_data = {
            "description": description,
        }
        response = await self.clients.a_update_client(  # type: ignore
            client_id=client_id,
            update_data=update_data,
        )
        return ClientResponse.model_validate(response)

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
        """
        self._ensure_configured()
        await self.clients.a_delete_client(client_id)  # type: ignore

    async def a_delete_clients(
        self,
        ids: List[str] | None = None,
        audiences: List[str] | None = None,
    ) -> None:
        """Delete multiple clients asynchronously.

        Parameters
        ----------
        ids : List[str] | None, optional
            The client IDs to filter for deletion.
            If None, all clients will be deleted.
            (not the one used for this request)
        audiences : List[str] | None, optional
            The audiences to filter.

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        await self.clients.a_delete_clients(ids, audiences)  # type: ignore

    def _ensure_configured(self) -> None:
        """Ensure the client is configured for use."""
        super()._ensure_configured()
        if not self.clients:  # pragma: no cover # raised in super
            raise ValueError(
                "Client is not configured. Call `configure()` first."
            )
