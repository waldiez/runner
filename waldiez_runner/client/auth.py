# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
#
"""Custom authentication for the Waldiez Runner client."""

import asyncio
import inspect
import logging
import threading
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Callable, Coroutine, Dict, Generator

import httpx

from .models import TokensResponse

LOG = logging.getLogger(__name__)


def get_default_base_url(passed_url: str) -> str:
    """Get the default base URL.

    Parameters
    ----------
    passed_url : str
        The passed URL

    Returns
    -------
    str
        The default base URL
    """
    url_parts = urllib.parse.urlsplit(passed_url)
    return f"{url_parts.scheme}://{url_parts.netloc}"


class Auth(httpx.Auth):
    """Custom authentication class."""

    def __init__(
        self,
        base_url: str | None = None,
        on_error: (
            Callable[[str], None]
            | Callable[[str], Coroutine[Any, Any, None]]
            | None
        ) = None,
        on_token: (
            Callable[[str], None]
            | Callable[[str], Coroutine[Any, Any, None]]
            | None
        ) = None,
    ) -> None:
        """Initialize the authentication class."""
        self._sync_lock = threading.RLock()
        self._async_lock = asyncio.Lock()
        self._base_url = get_default_base_url(base_url) if base_url else None
        self._client_id: str | None = None
        self._client_secret: str | None = None
        self._tokens_response: TokensResponse | None = None
        self.on_error = on_error
        self.on_token = on_token

    @property
    def base_url(self) -> str | None:
        """Get the base URL.

        Returns
        -------
        str
            The base URL
        """
        return self._base_url

    @property
    def token_endpoint(self) -> str | None:
        """Get the token endpoint.

        Returns
        -------
        str
            The token endpoint
        """
        return f"{self._base_url}/auth/token" if self._base_url else None

    @property
    def refresh_token_endpoint(self) -> str | None:
        """Get the refresh token endpoint.

        Returns
        -------
        str
            The refresh token endpoint
        """
        return (
            f"{self._base_url}/auth/token/refresh" if self._base_url else None
        )

    @property
    def client_id(self) -> str | None:
        """Get the client ID.

        Returns
        -------
        str
            The client ID
        """
        return self._client_id

    @property
    def client_secret(self) -> str | None:
        """Get the client secret.

        Returns
        -------
        str
            The client secret
        """
        return self._client_secret

    def has_valid_token(self) -> bool:
        """Check if the access token is valid.

        Returns
        -------
        bool
            True if the token is valid, False otherwise
        """
        return bool(self._tokens_response) and not self.is_token_expired()

    def configure(
        self, client_id: str, client_secret: str, base_url: str | None = None
    ) -> None:
        """Set the client ID and secret.

        Parameters
        ----------
        client_id : str
            The client ID
        client_secret : str
            The client secret
        base_url : str, optional
            The base URL (if not set in the constructor), by default None
        """
        self._client_id = client_id
        self._client_secret = client_secret
        if base_url is not None:
            self._base_url = get_default_base_url(base_url)

    def sync_get_token(self, force: bool = False) -> str | None:
        """Get a valid access token (synchronous).

        Parameters
        ----------
        force : bool, optional
            Force a new token fetch, by default False
        Returns
        -------
        str, optional
            The access token, or None if not available
        """
        with self._sync_lock:
            if force:
                self._fetch_token()
                if not self._tokens_response:  # pragma: no cover
                    return None
                return self._tokens_response.access_token
            if not self._tokens_response or self.is_token_expired():
                if self.is_refresh_token_expired():
                    self._fetch_token()
                else:
                    self._refresh_access_token()
            if (
                not self._tokens_response
                or not self._tokens_response.access_token
            ):
                return None
            return self._tokens_response.access_token

    def sync_auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """Attach the access token for sync requests.

        Parameters
        ----------
        request : httpx.Request
            The request

        Yields
        -------
        Generator[httpx.Request, httpx.Response, None]
            The request with the access token
        """
        request.headers["Authorization"] = f"Bearer {self.sync_get_token()}"
        yield request

    async def async_get_token(self, force: bool = False) -> str | None:
        """Get a valid access token (asynchronous).

        Parameters
        ----------
        force : bool, optional
            Force a new token fetch, by default False
        Returns
        -------
        str, optional
            The access token, or None if not available
        """
        async with self._async_lock:
            if force:
                await self._async_fetch_token()
                if (
                    not self._tokens_response
                    or not self._tokens_response.access_token
                ):  # pragma: no cover
                    return None
                return self._tokens_response.access_token
            if not self._tokens_response or self.is_token_expired():
                if self.is_refresh_token_expired():
                    await self._async_fetch_token()
                else:  # pragma: no cover
                    await self._async_refresh_access_token()
            if (
                not self._tokens_response
                or not self._tokens_response.access_token
            ):
                return None
            return self._tokens_response.access_token

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        """Attach the access token for async requests.

        Parameters
        ----------
        request : httpx.Request
            The request

        Yields
        -------
        AsyncGenerator[httpx.Request, httpx.Response]
            The request with the access token
        """
        request.headers["Authorization"] = (
            f"Bearer {await self.async_get_token()}"
        )
        yield request

    def is_token_expired(self) -> bool:
        """Check if the access token is expired.

        Returns
        -------
        bool
            True if the token is expired, False otherwise
        """
        return self._is_expired("expires_at")

    def is_refresh_token_expired(self) -> bool:
        """Check if the refresh token is expired.

        Returns
        -------
        bool
            True if the token is expired, False otherwise
        """
        return self._is_expired("refresh_expires_at")

    def _is_expired(self, key: str) -> bool:
        """Generic method to check if a token is (about to be) expired.

        Parameters
        ----------
        key : str
            The key to check in the token response

        Returns
        -------
        bool
            True if the token is expired, False otherwise
        """
        if not self._tokens_response:
            return True  # No token means it's effectively expired
        response_dump = self._tokens_response.model_dump()
        now_str = (
            datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        value = response_dump.get(key, now_str)
        if not value or not isinstance(value, str):  # pragma: no cover
            LOG.error("Invalid value for key '%s': '%s'", key, value)
            return True
        try:
            expires_at_dt = datetime.strptime(
                value,
                "%Y-%m-%dT%H:%M:%S.%fZ",
            ).replace(tzinfo=timezone.utc)
        except ValueError:  # pragma: no cover
            LOG.error("Invalid datetime format for key '%s': '%s'", key, value)
            response_dump["expires_at"] = now_str
            self._tokens_response = TokensResponse.model_validate(response_dump)
            return True

        return datetime.now(timezone.utc) >= expires_at_dt - timedelta(
            seconds=60
        )

    def _fetch_token(self) -> None:
        """Fetch a new access token (synchronous)."""
        if not self.client_id or not self.client_secret:
            LOG.error("Client ID and secret are not configured.")
            self._handle_error("Client ID and secret are not configured.")
            return
        if not self.token_endpoint:
            LOG.error("Token endpoint is not configured.")
            self._handle_error("Token endpoint is not configured.")
            return
        try:
            response = httpx.post(
                self.token_endpoint,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=30,
            )
        except httpx.HTTPError as exc:  # pragma: no cover
            LOG.error("Token fetch failed: %s", exc)
            self._handle_error(f"Token fetch failed: {exc}")
            return
        if response.status_code == 200:
            self._tokens_response = self._parse_token_response(response.json())
            self._handle_token(self._tokens_response.access_token)
        else:
            self._handle_error(f"Token fetch failed: {response.text}")

    async def _async_fetch_token(self) -> None:
        """Fetch a new access token (asynchronous)."""
        if not self._client_id or not self._client_secret:
            self._handle_error("Client ID and secret are not configured.")
            return
        if not self.token_endpoint:  # pragma: no cover
            self._handle_error("Token endpoint is not configured.")
            return
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_endpoint,
                    data={
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                )
        except httpx.HTTPError as exc:  # pragma: no cover
            self._handle_error(f"Token fetch failed: {exc}")
            return

        if response.status_code == 200:
            self._tokens_response = self._parse_token_response(response.json())
            self._handle_token(self._tokens_response.access_token)
        else:
            self._handle_error(f"Token fetch failed: {response.text}")

    def _refresh_access_token(self) -> None:
        """Refresh the access token (synchronous)."""
        if not self._tokens_response or not self._tokens_response.refresh_token:
            self._handle_error("No refresh token available for renewal.")
            return
        if not self.refresh_token_endpoint:  # pragma: no cover
            self._handle_error("Refresh token endpoint is not configured.")
            return
        try:
            response = httpx.post(
                self.refresh_token_endpoint,
                data={"refresh_token": self._tokens_response.refresh_token},
            )
        except httpx.HTTPError as exc:  # pragma: no cover
            self._handle_error(f"Failed to fetch token: {exc}")
            return

        if response.status_code == 200:
            self._tokens_response = self._parse_token_response(response.json())
            self._handle_token(self._tokens_response.access_token)
        else:  # pragma: no cover
            self._handle_error(f"Failed to refresh token: {response.text}")

    async def _async_refresh_access_token(self) -> None:
        """Refresh the access token (asynchronous)."""
        if not self._tokens_response or not self._tokens_response.access_token:
            self._handle_error("No refresh token available for renewal.")
            return
        if not self.refresh_token_endpoint:  # pragma: no cover
            self._handle_error("Refresh token endpoint is not configured.")
            return
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.refresh_token_endpoint,
                    data={"refresh_token": self._tokens_response.refresh_token},
                    timeout=30,
                )
        except httpx.HTTPError as exc:  # pragma: no cover
            self._handle_error(f"Failed to fetch token: {exc}")
            return
        if response.status_code == 200:
            self._tokens_response = self._parse_token_response(response.json())
            self._handle_token(self._tokens_response.access_token)
        else:  # pragma: no cover
            self._handle_error(f"Failed to refresh token: {response.text}")

    # pylint: disable=no-self-use
    def _parse_token_response(self, data: Dict[str, Any]) -> TokensResponse:
        """Parse and return the token response.

        Parameters
        ----------
        data : Dict[str, Any]
            The token response data

        Returns
        -------
        TokensResponse
            The parsed token response
        """
        expires_at = (
            (
                datetime.now(timezone.utc)
                + timedelta(seconds=int(data.get("expires_in", 3600)))
            )
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )

        refresh_expires_at = (
            (
                datetime.now(timezone.utc)
                + timedelta(seconds=int(data.get("refresh_expires_in", 86400)))
            )
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        audience = data.get("audience", "tasks-api")
        if audience not in ["tasks-api", "clients-api"]:
            audience = "tasks-api"
        return TokensResponse(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_type=data["token_type"],
            expires_at=expires_at,
            refresh_expires_at=refresh_expires_at,
            audience=audience,
        )

    def _handle_error(self, message: str) -> None:
        """Handle errors using the provided callback (sync or async).

        Parameters
        ----------
        message : str
            The error message
        """
        if self.on_error:
            if inspect.iscoroutinefunction(self.on_error):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.on_error(message))
                except RuntimeError:  # pragma: no cover
                    asyncio.run(self.on_error(message))
            else:
                self.on_error(message)

    def _handle_token(self, token: str) -> None:
        """Handle new tokens using the provided callback (sync or async).

        Parameters
        ----------
        token : str
            The new access token
        """
        if self.on_token:
            if inspect.iscoroutinefunction(self.on_token):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.on_token(token))
                except RuntimeError:  # pragma: no cover
                    asyncio.run(self.on_token(token))
            else:
                self.on_token(token)
