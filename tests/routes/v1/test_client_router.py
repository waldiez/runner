# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-function-docstring, missing-param-doc
# pylint: disable=missing-return-doc, missing-yield-doc, missing-raises-doc
"""Test client routes."""

from typing import AsyncGenerator
from unittest.mock import patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.types import CreateClientCallable
from waldiez_runner.config import Settings, SettingsManager
from waldiez_runner.main import get_app
from waldiez_runner.routes.v1.client_router import validate_clients_audience
from waldiez_runner.schemas.client import ClientCreateResponse


@pytest.fixture(name="client")
async def client_fixture(
    clients_api_client: ClientCreateResponse,
    settings: Settings,
) -> AsyncGenerator[AsyncClient, None]:
    """Get the FastAPI test client."""

    async def get_valid_api_client_id_mock() -> str:
        """Mock get_valid_client_id."""
        return clients_api_client.id

    # pylint: disable=duplicate-code
    with patch.object(SettingsManager, "load_settings", return_value=settings):
        app = get_app()
        app.dependency_overrides[validate_clients_audience] = (
            get_valid_api_client_id_mock
        )
        async with LifespanManager(app, startup_timeout=10) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app),
                base_url="http://test",
            ) as api_client:
                yield api_client


@pytest.mark.anyio
async def test_get_clients(client: AsyncClient) -> None:
    """Test get clients."""
    response = await client.get("/api/v1/clients")
    assert response.status_code == 200
    response_data = response.json()
    assert "items" in response_data
    assert "page" in response_data
    assert "total" in response_data
    assert len(response_data["items"]) > 0


@pytest.mark.anyio
async def test_get_clients_search_name(
    client: AsyncClient,
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test get clients with search."""
    c, _ = await create_client(
        async_session,
        name="Super Duper Client",
        description="Another client",
    )
    response = await client.get(
        "/api/v1/clients",
        params={"search": "Super Duper"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "items" in response_data
    assert "page" in response_data
    assert "total" in response_data
    assert len(response_data["items"]) > 0
    await async_session.delete(c)
    await async_session.commit()


@pytest.mark.anyio
async def test_get_clients_search_name_not_found(
    client: AsyncClient,
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test get clients with search not found."""
    c, _ = await create_client(
        async_session,
        name="Super Duper Client",
        description="Another client",
    )
    response = await client.get(
        "/api/v1/clients",
        params={"search": "Not Found"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "items" in response_data
    assert "page" in response_data
    assert "total" in response_data
    assert len(response_data["items"]) == 0
    await async_session.delete(c)
    await async_session.commit()


@pytest.mark.anyio
async def test_get_clients_search_description(
    client: AsyncClient,
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test get clients with search."""
    c, _ = await create_client(
        async_session,
        name="Super Duper Client",
        description="Another client",
    )
    response = await client.get(
        "/api/v1/clients",
        params={"search": "Another"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "items" in response_data
    assert "page" in response_data
    assert "total" in response_data
    assert len(response_data["items"]) > 0
    await async_session.delete(c)
    await async_session.commit()


@pytest.mark.anyio
async def test_get_clients_order_by(
    client: AsyncClient,
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test get clients with order by."""
    c, _ = await create_client(
        async_session,
        name="A Super Duper Client",
        description="Another client",
    )
    response = await client.get(
        "/api/v1/clients",
        params={"order_by": "name", "order_type": "asc"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "items" in response_data
    assert "page" in response_data
    assert "total" in response_data
    assert len(response_data["items"]) > 0
    assert response_data["items"][0]["name"] == "A Super Duper Client"
    await async_session.delete(c)
    await async_session.commit()


@pytest.mark.anyio
async def test_get_clients_order_by_desc(
    client: AsyncClient,
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test get clients with order by desc."""
    c1, _ = await create_client(
        async_session,
    )
    c, _ = await create_client(
        async_session,
        name="Z a super Duper Client",
        description="Another client",
    )
    response = await client.get(
        "/api/v1/clients",
        params={"order_by": "name", "order_type": "desc"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "items" in response_data
    assert "page" in response_data
    assert "total" in response_data
    assert len(response_data["items"]) > 0
    assert response_data["items"][0]["name"] == "Z a super Duper Client"
    await async_session.delete(c)
    await async_session.delete(c1)
    await async_session.commit()


@pytest.mark.anyio
async def test_get_clients_order_by_invalid(
    client: AsyncClient,
    async_session: AsyncSession,
    create_client: CreateClientCallable,
) -> None:
    """Test get clients with order by invalid."""
    c, _ = await create_client(
        async_session,
        name="A Super Duper Client",
        description="Another client",
    )
    response = await client.get(
        "/api/v1/clients",
        params={"order_by": "invalid", "order_type": "asc"},
    )
    assert response.status_code == 422
    await async_session.delete(c)
    await async_session.commit()


@pytest.mark.anyio
async def test_create_client(client: AsyncClient) -> None:
    """Test create client."""
    response = await client.post(
        "/api/v1/clients",
        json={"description": "Test Client"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "id" in response_data
    assert "client_secret" in response_data
    assert response_data["description"] == "Test Client"


@pytest.mark.anyio
async def test_get_client(
    client: AsyncClient, clients_api_client: ClientCreateResponse
) -> None:
    """Test get client."""
    response = await client.get(f"/api/v1/clients/{clients_api_client.id}")
    assert response.status_code == 200
    response_data = response.json()
    assert "id" in response_data
    assert "client_id" in response_data
    assert "client_secret" not in response_data
    assert "description" in response_data
    assert response_data["id"] == clients_api_client.id


@pytest.mark.anyio
async def test_get_client_not_found(client: AsyncClient) -> None:
    """Test get client not found."""
    response = await client.get("/api/v1/clients/invalid")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_update_client(
    client: AsyncClient, clients_api_client: ClientCreateResponse
) -> None:
    """Test update client."""
    response = await client.patch(
        f"/api/v1/clients/{clients_api_client.id}",
        json={"description": "Updated Client"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "id" in response_data
    assert "client_id" in response_data
    assert "client_secret" not in response_data
    assert "description" in response_data
    assert response_data["description"] == "Updated Client"


@pytest.mark.anyio
async def test_update_client_not_found(client: AsyncClient) -> None:
    """Test update client not found."""
    response = await client.patch(
        "/api/v1/clients/invalid",
        json={"description": "Updated Client"},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_delete_client(
    client: AsyncClient, tasks_api_client: ClientCreateResponse
) -> None:
    """Test delete client."""
    response = await client.delete(f"/api/v1/clients/{tasks_api_client.id}")
    assert response.status_code == 204


@pytest.mark.anyio
async def test_delete_client_not_found(client: AsyncClient) -> None:
    """Test delete client not found."""
    response = await client.delete("/api/v1/clients/invalid")
    assert response.status_code == 204


@pytest.mark.anyio
async def test_delete_not_own_client(
    client: AsyncClient, clients_api_client: ClientCreateResponse
) -> None:
    """Test delete not own client."""
    response = await client.delete(f"/api/v1/clients/{clients_api_client.id}")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_delete_clients(client: AsyncClient) -> None:
    """Test delete clients."""
    response = await client.delete("/api/v1/clients/")
    assert response.status_code == 204


@pytest.mark.anyio
async def test_delete_clients_with_audience(client: AsyncClient) -> None:
    """Test delete clients with audience."""
    response = await client.delete(
        "/api/v1/clients/",
        params={"audiences": "tasks-api"},
    )
    assert response.status_code == 204


@pytest.mark.anyio
async def test_delete_using_the_client_of_the_request(
    client: AsyncClient, clients_api_client: ClientCreateResponse
) -> None:
    """Test delete using the client of the request."""
    response = await client.delete(
        "/api/v1/clients/",
        params={"ids": clients_api_client.id},
    )
    assert response.status_code == 400
