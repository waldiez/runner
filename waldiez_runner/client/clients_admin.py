# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Waldiez serve client admin."""

from typing import Any, Callable, Coroutine, Dict, List

from ._clients_api import ClientsAPIClient
from .client_base import BaseClient


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

    def list_clients(self) -> Dict[str, Any]:
        """Retrieve the list of clients synchronously.

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
        return self.clients.list_clients()  # type: ignore

    def get_client(self, client_id: str) -> Dict[str, Any]:
        """Retrieve a specific client synchronously.

        Parameters
        ----------
        client_id : str
            The client ID

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
        return self.clients.get_client(client_id)  # type: ignore

    def create_client(
        self,
        client_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new client synchronously.

        Parameters
        ----------
        client_data : Dict[str, Any]
            The client data

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
        return self.clients.create_client(  # type: ignore
            client_data=client_data,
        )

    def update_client(
        self,
        client_id: str,
        update_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an existing client synchronously.

        Parameters
        ----------
        client_id : str
            The client ID
        update_data : Dict[str, Any]
            The data to update the client with

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
        return self.clients.update_client(  # type: ignore
            client_id=client_id,
            update_data=update_data,
        )

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

    def delete_clients(self, audiences: List[str] | None) -> None:
        """Delete multiple clients synchronously.

        Parameters
        ----------
        audiences : List[str] | None, optional
            The audiences to filter.

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        self.clients.delete_clients(audiences)  # type: ignore

    async def a_list_clients(self) -> Dict[str, Any]:
        """Retrieve the list of clients asynchronously.

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
        return await self.clients.a_list_clients()  # type: ignore

    async def a_get_client(self, client_id: str) -> Dict[str, Any]:
        """Retrieve a specific client asynchronously.

        Parameters
        ----------
        client_id : str
            The client ID

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
        return await self.clients.a_get_client(client_id)  # type: ignore

    async def a_create_client(
        self,
        client_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new client asynchronously.

        Parameters
        ----------
        client_data : Dict[str, Any]
            The client data

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
        return await self.clients.a_create_client(  # type: ignore
            client_data=client_data,
        )

    async def a_update_client(
        self,
        client_id: str,
        client_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an existing client asynchronously.

        Parameters
        ----------
        client_id : str
            The client ID
        client_data : Dict[str, Any]
            The client data

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
        return await self.clients.a_update_client(  # type: ignore
            client_id=client_id,
            update_data=client_data,
        )

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
        self, audiences: List[str] | None = None
    ) -> None:
        """Delete multiple clients asynchronously.

        Parameters
        ----------
        audiences : List[str] | None, optional
            The audiences to filter.

        Raises
        ------
        ValueError
            If the client is not configured
        """
        self._ensure_configured()
        await self.clients.a_delete_clients(audiences)  # type: ignore

    def _ensure_configured(self) -> None:
        """Ensure the client is configured for use."""
        super()._ensure_configured()
        if not self.clients:  # pragma: no cover # raised in super
            raise ValueError(
                "Client is not configured. Call `configure()` first."
            )
