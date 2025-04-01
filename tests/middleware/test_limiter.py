# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-return-type-doc,missing-param-doc

"""Tests for the rate limiter middleware."""

from typing import Dict

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from waldiez_runner.middleware.limiter import (
    add_rate_limiter,
    get_real_ip,
    limiter,
)


@pytest.fixture(name="app")
def app_fixture() -> FastAPI:
    """Create a FastAPI app with rate limiting."""
    app = FastAPI()

    add_rate_limiter(app)

    # pylint: disable=unused-argument
    @app.get("/limited")
    @limiter.limit("3/minute")
    async def limited_endpoint(request: Request) -> Dict[str, str]:
        """Limited endpoint."""
        return {"message": "Success"}

    @app.get("/unlimited")
    async def unlimited_endpoint(request: Request) -> Dict[str, str]:
        """Unlimited endpoint."""
        return {"message": "No limit"}

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
            headers: Dict[str, str] | None = None,
            client_host: str | None = None,
        ) -> None:
            """Initialize the mock request."""
            self.headers = headers or {}
            self.client = type("Client", (), {"host": client_host})

    headers = {
        "X-Forwarded-For": "192.168.1.1, 10.0.0.1",
        "X-Real-IP": "10.0.0.2",
    }

    request = MockRequest(
        headers=headers,
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
    response = client.get("/unlimited")
    assert response.status_code == 200
    assert response.json() == {"message": "No limit"}
