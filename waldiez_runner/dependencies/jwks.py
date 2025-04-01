# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""JSON Web Key Set (JWKS) utilities."""

import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict

import httpx

if TYPE_CHECKING:
    from waldiez_runner.config import Settings


# pylint: disable=too-few-public-methods
class JWKSCache:
    """Cache for JWKS keys."""

    def __init__(self, settings: "Settings"):
        """Initialize the JWKS cache.

        Parameters
        ----------
        settings : Settings
            The settings instance.
        """
        self.settings = settings
        self.cache_ttl = settings.oidc_jwks_cache_ttl
        self._cache: Dict[str, Any] | None = None
        self._cache_expiry = 0.0
        self._lock = asyncio.Lock()
        if settings.use_oidc_auth and not settings.oidc_jwks_url:
            raise ValueError("OIDC JWKS URL is required for OIDC auth")
        self.jwks_url = str(settings.oidc_jwks_url)
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=5),
        )

    async def get_keys(self) -> Dict[str, Any]:
        """Get JWKS keys, refresh cache if expired (async-safe).

        Returns
        -------
        Dict[str, Any]
            The JWKS keys.
        """
        # Fast path: use cache if still valid
        if self._cache and time.time() < self._cache_expiry:
            return self._cache

        # Slow path: Acquire lock and fetch keys if still expired
        async with self._lock:
            # Double-checked locking (another coroutine might have refreshed it)
            if (
                self._cache and time.time() < self._cache_expiry
            ):  # pragma: no cover
                return self._cache

            response = await self._http_client.get(self.jwks_url)
            response.raise_for_status()
            keys = response.json()
            self._cache_expiry = time.time() + self.cache_ttl
            self._cache = keys
            return keys
