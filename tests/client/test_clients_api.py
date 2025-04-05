# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# flake8: noqa: E501
# pylint: disable=missing-param-doc,missing-return-doc,protected-access
"""Test waldiez_runner.client._clients_api.*."""

import httpx
import pytest
from pytest_httpx import HTTPXMock

from waldiez_runner.client._clients_api import ClientsAPIClient
from waldiez_runner.client.auth import CustomAuth


@pytest.fixture(name="client")
def client_fixture(auth: CustomAuth) -> ClientsAPIClient:
    """Return a new ClientsAPIClient instance."""
    return ClientsAPIClient(auth)


def test_configure(client: ClientsAPIClient, auth: CustomAuth) -> None:
    """Test client configuration."""
    assert client._auth == auth
    assert client._auth.base_url == "http://localhost:8000"


def test_configure_raises_without_base_url() -> None:
    """Test that configure raises if base_url is not set."""
    auth = CustomAuth()
    auth._base_url = None

    client = ClientsAPIClient(auth=None)
    with pytest.raises(ValueError, match="Base URL is required"):
        client.configure(auth)


def test_list_clients(client: ClientsAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test listing clients."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/clients",
        json={"items": [{"id": "1"}, {"id": "2"}], "total": 2},
        status_code=200,
    )
    response = client.list_clients()
    assert response == {"items": [{"id": "1"}, {"id": "2"}], "total": 2}


def test_get_client(client: ClientsAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test getting a client."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/clients/test-id",
        json={"id": "test-id", "name": "Test Client"},
        status_code=200,
    )

    response = client.get_client("test-id")
    assert response == {"id": "test-id", "name": "Test Client"}


def test_create_client(client: ClientsAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test creating a client."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/clients",
        json={"id": "new-client"},
        status_code=201,
    )

    response = client.create_client({"name": "New Client"})
    assert response == {"id": "new-client"}


def test_update_client(client: ClientsAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test updating a client."""
    httpx_mock.add_response(
        method="PATCH",
        url="http://localhost:8000/api/v1/clients/test-id",
        json={"id": "test-id", "name": "Updated Name"},
        status_code=200,
    )

    response = client.update_client("test-id", {"name": "Updated Name"})
    assert response == {"id": "test-id", "name": "Updated Name"}


def test_delete_client(client: ClientsAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test deleting a client."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/clients/test-id",
        status_code=204,
    )

    client.delete_client("test-id")


def test_delete_clients(
    client: ClientsAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test deleting all clients."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/clients",
        status_code=204,
    )

    client.delete_clients()


@pytest.mark.anyio
async def test_a_list_clients(
    client: ClientsAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test async list clients."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/clients",
        json={"items": [{"id": "1"}], "total": 1},
        status_code=200,
    )
    response = await client.a_list_clients()
    assert response["total"] == 1


@pytest.mark.anyio
async def test_a_get_client(
    client: ClientsAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test async get client."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/clients/test-id",
        json={"id": "test-id", "name": "Test Client"},
        status_code=200,
    )

    response = await client.a_get_client("test-id")
    assert response == {"id": "test-id", "name": "Test Client"}


@pytest.mark.anyio
async def test_a_create_client(
    client: ClientsAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test async create client."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/clients",
        json={"id": "new-client"},
        status_code=201,
    )

    response = await client.a_create_client({"name": "New Client"})
    assert response == {"id": "new-client"}


@pytest.mark.anyio
async def test_a_update_client(
    client: ClientsAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test async update client."""
    httpx_mock.add_response(
        method="PATCH",
        url="http://localhost:8000/api/v1/clients/test-id",
        json={"id": "test-id", "name": "Updated Name"},
        status_code=200,
    )

    response = await client.a_update_client("test-id", {"name": "Updated Name"})
    assert response == {"id": "test-id", "name": "Updated Name"}


@pytest.mark.anyio
async def test_a_delete_client(
    client: ClientsAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test async delete client."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/clients/test-id",
        status_code=204,
    )

    await client.a_delete_client("test-id")


@pytest.mark.anyio
async def test_a_delete_clients(
    client: ClientsAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test async delete all clients."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/clients",
        status_code=204,
    )

    await client.a_delete_clients()


def test_list_clients_error(
    client: ClientsAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test list clients HTTP error."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/clients",
        status_code=500,
        text="Error",
    )
    with pytest.raises(httpx.HTTPError):
        client.list_clients()


@pytest.mark.anyio
async def test_a_list_clients_error(
    client: ClientsAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test async list clients HTTP error."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/clients",
        status_code=500,
        text="Error",
    )
    with pytest.raises(httpx.HTTPError):
        await client.a_list_clients()
