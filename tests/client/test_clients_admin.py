# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-return-doc
# pylint: disable=protected-access,unused-argument
"""Test waldiez_runner.client._clients_admin.*."""

import pytest
from pytest_httpx import HTTPXMock

from waldiez_runner.client.auth import Auth
from waldiez_runner.client.clients_admin import ClientsAdmin


@pytest.fixture(name="clients_admin")
def clients_admin_fixture(auth: Auth) -> ClientsAdmin:
    """Return a new ClientsAdmin instance."""
    assert auth.base_url is not None
    assert auth.client_id is not None
    assert auth.client_secret is not None
    admin = ClientsAdmin()
    admin.configure(
        auth.base_url,
        auth.client_id,
        auth.client_secret,
    )
    return admin


def test_configure_sets_clients(clients_admin: ClientsAdmin) -> None:
    """Test configure sets the ClientsAPIClient instance."""
    assert clients_admin.clients is not None


def test_ensure_configured_raises() -> None:
    """Test _ensure_configured raises ValueError if not configured."""
    admin = ClientsAdmin()
    with pytest.raises(ValueError):
        admin._ensure_configured()


def test_list_clients(
    httpx_mock: HTTPXMock,
    clients_admin: ClientsAdmin,
) -> None:
    """Test listing clients synchronously."""
    httpx_mock.add_response(
        method="GET",
        url=f"{clients_admin.base_url}/api/v1/clients",
        json={"items": [], "total": 0, "page": 1, "size": 50, "pages": 1},
    )
    assert clients_admin.list_clients().model_dump() == {
        "items": [],
        "total": 0,
        "page": 1,
        "size": 50,
        "pages": 1,
    }


def test_get_client(
    httpx_mock: HTTPXMock,
    clients_admin: ClientsAdmin,
) -> None:
    """Test retrieving a single client synchronously."""
    httpx_mock.add_response(
        method="GET",
        url=f"{clients_admin.base_url}/api/v1/clients/client123",
        json={
            "client_id": "client123",
            "id": "id",
            "audience": "tasks-api",
            "name": "name",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        },
    )
    result = clients_admin.get_client("client123").model_dump()
    assert result["client_id"] == "client123"


def test_create_client(
    httpx_mock: HTTPXMock,
    clients_admin: ClientsAdmin,
) -> None:
    """Test creating a client synchronously."""
    httpx_mock.add_response(
        method="POST",
        url=f"{clients_admin.base_url}/api/v1/clients",
        json={
            "name": "name",
            "description": "new_description",
            "client_id": "created",
            "audience": "tasks-api",
            "id": "client1",
            "client_secret": "super_secret",  # nosemgrep # nosec
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        },
    )
    result = clients_admin.create_client(
        {
            "client_id": "created",
            "description": "new_description",
        }
    ).model_dump()
    assert result["client_id"] == "created"
    assert result["description"] == "new_description"


def test_update_client(
    httpx_mock: HTTPXMock,
    clients_admin: ClientsAdmin,
) -> None:
    """Test updating a client synchronously."""
    httpx_mock.add_response(
        method="PATCH",
        url=f"{clients_admin.base_url}/api/v1/clients/client123",
        json={
            "client_id": "client123",
            "name": "name",
            "description": "updated",
            "id": "id",
            "audience": "tasks-api",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        },
    )
    result = clients_admin.update_client(
        "client123", description="updated"
    ).model_dump()
    assert result["description"] == "updated"


def test_delete_client(
    httpx_mock: HTTPXMock,
    clients_admin: ClientsAdmin,
) -> None:
    """Test deleting a client synchronously."""
    httpx_mock.add_response(
        method="DELETE",
        url=f"{clients_admin.base_url}/api/v1/clients/client123",
        status_code=204,
    )
    clients_admin.delete_client(
        "client123"
    )  # No assertion, just ensure no error


def test_delete_clients(
    httpx_mock: HTTPXMock,
    clients_admin: ClientsAdmin,
) -> None:
    """Test deleting multiple clients synchronously."""
    audiences = "&".join(
        f"audiences={audience}" for audience in ["tasks-api", "clients-api"]
    )
    url = f"{clients_admin.base_url}/api/v1/clients?{audiences}"
    httpx_mock.add_response(
        method="DELETE",
        url=url,
        status_code=204,
    )
    clients_admin.delete_clients(None, audiences=["tasks-api", "clients-api"])


@pytest.mark.anyio
async def test_a_list_clients(
    httpx_mock: HTTPXMock,
    clients_admin: ClientsAdmin,
) -> None:
    """Test listing clients asynchronously."""
    httpx_mock.add_response(
        method="GET",
        url=f"{clients_admin.base_url}/api/v1/clients",
        json={"items": [], "total": 0, "page": 1, "size": 50, "pages": 1},
    )
    result = await clients_admin.a_list_clients()
    assert result.items == []


@pytest.mark.anyio
async def test_a_get_client(
    httpx_mock: HTTPXMock,
    clients_admin: ClientsAdmin,
) -> None:
    """Test getting client asynchronously."""
    httpx_mock.add_response(
        method="GET",
        url=f"{clients_admin.base_url}/api/v1/clients/client123",
        json={
            "client_id": "client123",
            "id": "id",
            "audience": "tasks-api",
            "name": "name",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        },
    )
    result = await clients_admin.a_get_client("client123")
    assert result.client_id == "client123"


@pytest.mark.anyio
async def test_a_create_client(
    httpx_mock: HTTPXMock,
    clients_admin: ClientsAdmin,
) -> None:
    """Test creating a client asynchronously."""
    httpx_mock.add_response(
        method="POST",
        url=f"{clients_admin.base_url}/api/v1/clients",
        json={
            "client_id": "new",
            "id": "id",
            "name": "name",
            "audience": "tasks-api",
            "client_secret": "super_secret",  # nosemgrep # nosec
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        },
    )
    result = await clients_admin.a_create_client({"client_id": "new"})
    assert result.client_id == "new"


@pytest.mark.anyio
async def test_a_update_client(
    httpx_mock: HTTPXMock,
    auth: Auth,
    clients_admin: ClientsAdmin,
) -> None:
    """Test updating a client asynchronously."""
    httpx_mock.add_response(
        method="PATCH",
        url=f"{clients_admin.base_url}/api/v1/clients/client123",
        json={
            "client_id": "client123",
            "description": "updated",
            "id": "id",
            "audience": "tasks-api",
            "name": "name",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        },
    )
    result = await clients_admin.a_update_client(
        "client123", description="updated"
    )
    assert result.description == "updated"


@pytest.mark.anyio
async def test_a_delete_client(
    httpx_mock: HTTPXMock,
    clients_admin: ClientsAdmin,
) -> None:
    """Test deleting a client asynchronously."""
    httpx_mock.add_response(
        method="DELETE",
        url=f"{clients_admin.base_url}/api/v1/clients/client123",
        status_code=204,
    )
    await clients_admin.a_delete_client("client123")  # Should not raise


@pytest.mark.anyio
async def test_a_delete_clients(
    httpx_mock: HTTPXMock,
    clients_admin: ClientsAdmin,
) -> None:
    """Test deleting multiple clients asynchronously."""
    url = f"{clients_admin.base_url}/api/v1/clients?audiences=a1&audiences=a2"
    httpx_mock.add_response(
        method="DELETE",
        url=url,
        status_code=204,
    )
    await clients_admin.a_delete_clients(None, ["a1", "a2"])
