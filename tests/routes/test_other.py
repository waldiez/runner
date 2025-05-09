# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,unused-argument
# pylint: disable=missing-param-doc,unused-argument,missing-yield-doc

"""Test waldiez_runner.routes.other.*."""

from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from waldiez_runner.config import Settings, SettingsManager
from waldiez_runner.main import get_app
from waldiez_runner.routes.other import validate_clients_audience
from waldiez_runner.schemas.client import ClientCreateResponse

ROOT_MODULE = "waldiez_runner"


@pytest.fixture(name="client")
async def client_fixture(
    tasks_api_client: ClientCreateResponse,
    settings: Settings,
) -> AsyncGenerator[AsyncClient, None]:
    """Get the FastAPI test client."""

    async def get_valid_api_client_id_mock() -> str:
        """Mock get_valid_client_id."""
        return tasks_api_client.id

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
async def test_health_endpoint(client: AsyncClient) -> None:
    """Test the health check endpoints."""
    response = await client.get("/health")
    assert response.status_code == 200

    response = await client.get("/healthz")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_openapi_endpoint(client: AsyncClient) -> None:
    """Test the OpenAPI endpoint."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_robot_txt(client: AsyncClient) -> None:
    """Test the robots.txt endpoint."""
    response = await client.get("/robots.txt")
    assert response.status_code == 200
    assert response.text == "User-agent: *\nDisallow: /"


@pytest.mark.anyio
async def test_status_unauthorized(client: AsyncClient) -> None:
    """Test getting the status of the application."""
    with (
        patch(
            f"{ROOT_MODULE}.routes.other.TaskService.get_active_tasks",
            new_callable=AsyncMock,
        ) as mock_active,
        patch(
            f"{ROOT_MODULE}.routes.other.TaskService.get_pending_tasks",
            new_callable=AsyncMock,
        ) as mock_pending,
    ):
        mock_active.return_value = []
        mock_pending.return_value = []
        response = await client.get("/status")
        assert response.status_code == 200
        status_dict = response.json()
        assert status_dict["healthy"] is True
        assert status_dict["active_tasks"] == 0
        assert status_dict["pending_tasks"] == 0
        assert isinstance(status_dict["max_capacity"], int)
        assert isinstance(status_dict["cpu_percent"], float)
        assert isinstance(status_dict["memory_percent"], float)


@pytest.mark.anyio
async def test_catch_all(client: AsyncClient) -> None:
    """Test the catch all route."""
    response = await client.get("/random")
    assert response.status_code == 404
