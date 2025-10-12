# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-yield-doc,missing-param-doc
# pylint: disable=unused-argument
# pyright: reportUnusedFunction=false

"""Test the conditional gzip middleware."""

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from waldiez_runner.middleware.conditional_gzip import ConditionalGZipMiddleware


@pytest.fixture(name="client_all_enabled")
async def client_all_enabled_fixture() -> AsyncGenerator[AsyncClient, None]:
    """App with gzip enabled on all routes."""
    app = FastAPI()

    @app.get("/gzip")
    async def gzip_route() -> JSONResponse:
        """Route that should be compressed."""
        return JSONResponse({"message": "this should be compressed"})

    app.add_middleware(ConditionalGZipMiddleware, minimum_size=10)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as api_client:
        yield api_client


@pytest.fixture(name="client_conditional")
async def client_conditional_fixture() -> AsyncGenerator[AsyncClient, None]:
    """App with gzip conditionally enabled based on pattern."""
    app = FastAPI()

    # noinspection PyUnusedLocal
    @app.get("/api/v1/tasks/{task_id}/download")
    async def excluded_route(task_id: str) -> JSONResponse:
        """Route that should not be compressed."""
        return JSONResponse({"message": "do not compress this"})

    @app.get("/zip")
    async def included_route() -> JSONResponse:
        """Route that should be compressed."""
        return JSONResponse({"message": "compress this"})

    app.add_middleware(
        ConditionalGZipMiddleware,
        exclude_patterns=[r"^/api/v1/tasks/.+/download$"],
        minimum_size=10,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as api_client:
        yield api_client


@pytest.mark.anyio
async def test_gzip_applied_when_not_excluded(
    client_all_enabled: AsyncClient,
) -> None:
    """GZip should be applied when not excluded."""
    response = await client_all_enabled.get(
        "/gzip", headers={"Accept-Encoding": "gzip"}
    )
    assert response.status_code == 200
    assert response.headers.get("Content-Encoding") == "gzip"


@pytest.mark.anyio
async def test_gzip_skipped_on_excluded_route(
    client_conditional: AsyncClient,
) -> None:
    """GZip should be skipped for excluded paths."""
    response = await client_conditional.get(
        "/api/v1/tasks/123/download", headers={"Accept-Encoding": "gzip"}
    )
    assert response.status_code == 200
    assert "Content-Encoding" not in response.headers


@pytest.mark.anyio
async def test_gzip_applied_on_included_route(
    client_conditional: AsyncClient,
) -> None:
    """GZip should be applied when route is not excluded."""
    response = await client_conditional.get(
        "/zip", headers={"Accept-Encoding": "gzip"}
    )
    assert response.status_code == 200
    assert response.headers.get("Content-Encoding") == "gzip"
