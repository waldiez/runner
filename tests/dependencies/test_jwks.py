# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-return-doc,missing-yield-doc
# pylint: disable=too-few-public-methods,protected-access
"""Test waldiez_runner.dependencies.auth.jwks*."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from pytest_httpx import HTTPXMock

from waldiez_runner.dependencies.jwks import JWKSCache


# pylint: disable=too-few-public-methods
class MockSettings:
    """Mock Settings class to simulate required settings."""

    def __init__(
        self,
        use_oidc_auth: bool = True,
        oidc_jwks_url: str | None = "https://example.com/jwks",
        oidc_jwks_cache_ttl: int = 60,
    ) -> None:
        """Initialize the mock settings."""
        self.use_oidc_auth = use_oidc_auth
        self.oidc_jwks_url = oidc_jwks_url
        self.oidc_jwks_cache_ttl = oidc_jwks_cache_ttl


@pytest.fixture(name="settings")
def settings_fixture() -> MockSettings:
    """Fixture for mock settings."""
    return MockSettings()


@pytest_asyncio.fixture(name="jwks_cache")
async def jwks_cache_fixture(settings: MockSettings) -> JWKSCache:
    """Fixture for JWKSCache instance."""
    return JWKSCache(settings)  # type: ignore


def test_jwks_cache_init(settings: MockSettings) -> None:
    """Test JWKSCache initialization."""
    cache = JWKSCache(settings)  # type: ignore
    assert cache.jwks_url == settings.oidc_jwks_url
    assert cache.cache_ttl == settings.oidc_jwks_cache_ttl
    assert cache._cache is None
    assert cache._cache_expiry == 0.0


def test_jwks_cache_missing_url() -> None:
    """Test that missing OIDC JWKS URL raises an error."""
    with pytest.raises(
        ValueError, match="OIDC JWKS URL is required for OIDC auth"
    ):
        JWKSCache(
            MockSettings(use_oidc_auth=True, oidc_jwks_url=None)  # type: ignore
        )


@pytest.mark.asyncio
async def test_jwks_cache_get_keys_cached(jwks_cache: JWKSCache) -> None:
    """Test that cached keys are returned if still valid."""
    jwks_cache._cache = {"keys": ["mocked_key"]}
    jwks_cache._cache_expiry = time.time() + 10

    keys = await jwks_cache.get_keys()
    assert keys == {"keys": ["mocked_key"]}


@pytest.mark.asyncio
async def test_jwks_cache_get_keys_refresh(jwks_cache: JWKSCache) -> None:
    """Test that keys are fetched if cache is expired."""
    jwks_cache._cache = None
    jwks_cache._cache_expiry = 0

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"keys": ["new_mocked_key"]})

    with patch("httpx.AsyncClient.get", return_value=mock_response) as mock_get:
        keys = await jwks_cache.get_keys()

    assert keys == {"keys": ["new_mocked_key"]}
    assert jwks_cache._cache == {"keys": ["new_mocked_key"]}
    assert jwks_cache._cache_expiry > time.time()
    mock_get.assert_called_once_with(jwks_cache.jwks_url)


@pytest.mark.asyncio
async def test_jwks_cache_get_keys_http_error(jwks_cache: JWKSCache) -> None:
    """Test that an HTTP error raises an exception."""
    with patch(
        "httpx.AsyncClient.get",
        side_effect=httpx.HTTPStatusError(
            "Mocked HTTP error",
            request=None,  # type: ignore
            response=None,  # type: ignore
        ),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await jwks_cache.get_keys()


@pytest.mark.asyncio
async def test_jwks_cache_concurrent_requests(
    jwks_cache: JWKSCache, httpx_mock: HTTPXMock
) -> None:
    """Test that concurrent requests to get_keys are properly synchronized."""
    httpx_mock.reset()
    jwks_cache._cache = None
    jwks_cache._cache_expiry = 0  # Force refresh

    httpx_mock.add_response(json={"keys": ["concurrent_mocked_key"]})
    tasks = [jwks_cache.get_keys() for _ in range(5)]
    results = await asyncio.gather(*tasks)

    for result in results:
        assert result == {"keys": ["concurrent_mocked_key"]}

    assert len(httpx_mock.get_requests()) == 1
    # Ensure only one HTTP request was made
    # mock_get.assert_awaited_once_with(jwks_cache.jwks_url)
