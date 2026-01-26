# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=missing-return-doc,unused-argument
# pylint: disable=missing-param-doc,unused-argument,missing-yield-doc

"""Test waldiez_runner.routes.auth.*."""

import time
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from waldiez_runner.config import Settings, SettingsManager
from waldiez_runner.main import get_app
from waldiez_runner.schemas.client import ClientCreateResponse

ROOT_MODULE = "waldiez_runner"


@pytest.fixture(name="client")
async def client_fixture(
    settings: Settings,
    clients_api_client: ClientCreateResponse,
    tasks_api_client: ClientCreateResponse,
) -> AsyncGenerator[AsyncClient, None]:
    """Get the FastAPI test client."""

    with patch.object(SettingsManager, "load_settings", return_value=settings):
        app = get_app()
        async with LifespanManager(app, startup_timeout=10) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app),
                base_url="http://test",
            ) as api_client:
                yield api_client


@pytest.mark.anyio
async def test_get_token_clients_api_aud(
    client: AsyncClient,
    clients_api_client: ClientCreateResponse,
) -> None:
    """Test get token for clients API audience."""
    # noinspection DuplicatedCode
    response = await client.post(
        "/auth/token/",
        data={
            "client_id": clients_api_client.client_id,
            "client_secret": clients_api_client.client_secret,
        },
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "access_token" in response_data
    assert "refresh_token" in response_data
    assert "token_type" in response_data
    assert "expires_at" in response_data
    assert "refresh_expires_at" in response_data
    assert "audience" in response_data
    assert response_data["audience"] == "clients-api"


@pytest.mark.anyio
async def test_get_token_tasks_api_aud(
    client: AsyncClient,
    async_session: AsyncSession,
    tasks_api_client: ClientCreateResponse,
) -> None:
    """Test get token for tasks API audience."""
    # noinspection DuplicatedCode
    response = await client.post(
        "/auth/token/",
        data={
            "client_id": tasks_api_client.client_id,
            "client_secret": tasks_api_client.client_secret,
        },
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "access_token" in response_data
    assert "refresh_token" in response_data
    assert "token_type" in response_data
    assert "expires_at" in response_data
    assert "refresh_expires_at" in response_data
    assert "audience" in response_data
    assert response_data["audience"] == "tasks-api"


@pytest.mark.anyio
async def test_get_token_with_invalid_credentials(
    client: AsyncClient,
    clients_api_client: ClientCreateResponse,
) -> None:
    """Test get token with invalid credentials."""
    response = await client.post(
        "/auth/token/",
        data={
            "client_id": clients_api_client.id,  # instead of client_id
            "client_secret": clients_api_client.client_secret,
        },
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_refresh_a_token(
    client: AsyncClient,
    tasks_api_client: ClientCreateResponse,
) -> None:
    """Test refresh a token."""
    token_response = await client.post(
        "/auth/token/",
        data={
            "client_id": tasks_api_client.client_id,
            "client_secret": tasks_api_client.client_secret,
        },
    )
    assert token_response.status_code == 200
    token_response_data = token_response.json()
    refresh_token = token_response_data["refresh_token"]
    audience = token_response_data["audience"]
    time.sleep(1)  # just to make sure the expiry/new token is different
    response = await client.post(
        "/auth/token/refresh/",
        json={
            "refresh_token": refresh_token,
            "audience": audience,
        },
    )
    assert response.status_code == 200
    response_data = response.json()
    assert "access_token" in response_data
    assert "refresh_token" in response_data
    assert refresh_token != response_data["refresh_token"]
    assert "audience" in response_data
    assert response_data["audience"] == audience


@pytest.mark.anyio
async def test_refresh_a_token_with_invalid_token(
    client: AsyncClient,
    tasks_api_client: ClientCreateResponse,
) -> None:
    """Test refresh a token with invalid token."""
    response = await client.post(
        "/auth/token/refresh/",
        json={
            "refresh_token": "invalid",  # nosemgrep # nosec
            "audience": "tasks-api",
        },
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_refresh_a_token_with_invalid_audience(
    client: AsyncClient,
    tasks_api_client: ClientCreateResponse,
) -> None:
    """Test refresh a token with invalid audience."""
    token_response = await client.post(
        "/auth/token/",
        data={
            "client_id": tasks_api_client.client_id,
            "client_secret": tasks_api_client.client_secret,
        },
    )
    assert token_response.status_code == 200
    refresh_token = token_response.json()["refresh_token"]
    response = await client.post(
        "/auth/token/refresh/",
        json={
            "refresh_token": refresh_token,
            "audience": "invalid",
        },
    )
    assert response.status_code == 401
