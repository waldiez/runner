# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-return-type-doc,missing-param-doc
# pyright: reportUnusedFunction=false,reportUnknownMemberType=false
# pyright: reportUntypedFunctionDecorator=false

"""Tests for the rate limiter middleware."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from waldiez_runner.middleware.slow_api import (
    add_rate_limiter,
    get_real_ip,
)


@pytest.fixture(name="app")
def app_fixture() -> FastAPI:
    """Create a FastAPI app with rate limiting."""
    app = FastAPI()
    to_exclude = r"^/api/v1/tasks/[^/]+/download/?$"
    limiter = add_rate_limiter(app, exclude_patterns=[to_exclude])

    # pylint: disable=unused-argument
    # noinspection PyUnusedLocal
    @app.get("/limited")
    @limiter.limit("3/minute")
    async def limited_endpoint(request: Request) -> dict[str, str]:
        """Limited endpoint."""
        return {"message": "Success"}

    # noinspection PyUnusedLocal
    @app.get("/unlimited")
    @limiter.exempt  # type: ignore
    async def unlimited_endpoint(request: Request) -> dict[str, str]:
        """Unlimited endpoint."""
        return {"message": "No limit"}

    @app.get("/api/v1/tasks/task12-34/download")
    @app.get("/api/v1/tasks/task12-34/download/")
    async def download_task(request: Request) -> dict[str, str]:
        return {"here": "you are"}

    return app


@pytest.fixture(name="client")
def client_fixture(app: FastAPI) -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_get_real_ip() -> None:
    """Test get_real_ip."""

    # pylint: disable=too-few-public-methods
    class MockRequest:
        """Mock request class."""

        def __init__(
            self,
            headers: dict[str, str] | None = None,
            client_host: str | None = None,
        ) -> None:
            """Initialize the mock request."""
            self.headers = headers or {}
            self.client = type("Client", (), {"host": client_host})

    request_headers = {
        "X-Forwarded-For": "192.168.1.1, 10.0.0.1",
        "X-Real-IP": "10.0.0.2",
    }

    request = MockRequest(
        headers=request_headers,
        client_host="127.0.0.1",
    )
    assert get_real_ip(request) == "192.168.1.1"  # type: ignore

    request.headers.pop("X-Forwarded-For")
    assert get_real_ip(request) == "10.0.0.2"  # type: ignore

    request.headers.pop("X-Real-IP")
    assert get_real_ip(request) == "127.0.0.1"  # type: ignore


def test_rate_limit_exceeded(client: TestClient) -> None:
    """Test rate limit exceeded."""
    for _ in range(3):
        response = client.get("/limited")
        assert response.status_code == 200

    # 4th request should hit the limit
    response = client.get("/limited")
    assert response.status_code == 429
    assert "error" in response.json()


def test_unlimited_endpoint(client: TestClient) -> None:
    """Test unlimited endpoint."""
    for _ in range(4):
        response = client.get("/unlimited")
        assert response.status_code == 200
        assert response.json() == {"message": "No limit"}


def test_excluded_endpoint(client: TestClient) -> None:
    """Test excluding endpoint."""
    for _ in range(4):
        response = client.get("/api/v1/tasks/task12-34/download")
        assert response.status_code == 200
    for _ in range(4):
        response = client.get("/api/v1/tasks/task12-34/download/")
        assert response.status_code == 200
