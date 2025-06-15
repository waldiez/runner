# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""App dependency getters."""

from typing import Any, AsyncGenerator, Callable, Coroutine, Dict, List

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from waldiez_runner.config import Settings
from waldiez_runner.models import Base
from waldiez_runner.services.client_service import ClientService

from .auth import get_client_id_from_token, verify_external_auth_token
from .context import RequestContext, get_request_context
from .jwks import JWKSCache
from .lifecycle import app_state
from .storage import Storage, get_storage_backend

bearer_scheme = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get the database session.

    Yields
    ------
    AsyncSession
        The database session.

    Raises
    ------
    RuntimeError
        If the database is not initialized.
    """
    if not app_state.db or not app_state.db.engine:
        raise RuntimeError("Database not initialized")
    async with app_state.db.session() as session:
        if app_state.db.is_sqlite:
            # make sure the tables are created
            async with app_state.db.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        yield session


def get_client_id(
    *expected_audiences: str, allow_external_auth: bool = True
) -> Callable[
    [HTTPAuthorizationCredentials],
    Coroutine[Any, Any, str],
]:
    """Require a specific audience for the request.

    Parameters
    ----------
    *expected_audiences : str
        The expected audiences.
    allow_external_auth : bool, optional
        Whether to allow external authentication, by default True

    Returns
    -------
    Callable[[HTTPAuthorizationCredentials],Coroutine[Any, Any, str]]
        The dependency.
    """

    async def dependency(
        credentials: Annotated[
            HTTPAuthorizationCredentials, Security(bearer_scheme)
        ],
        session: AsyncSession = Depends(get_db),
        context: RequestContext = Depends(get_request_context),
    ) -> str:
        """Check the audience of the JWT payload.

        Parameters
        ----------
        credentials : HTTPAuthorizationCredentials
            The authorization credentials.
        session : AsyncSession
            The database session.
        context : RequestContext
            The request context.

        Returns
        -------
        str
            The subject of the JWT or "external" for external tokens.

        Raises
        ------
        HTTPException
            If the audience is not as expected.
        RuntimeError
            If the settings or JWKs cache are not initialized.
        """
        token = credentials.credentials
        scheme = credentials.scheme
        audience: str | List[str] | None = None
        if expected_audiences:
            audience = (
                list(expected_audiences)
                if len(expected_audiences) > 1
                else (
                    expected_audiences[0]
                    if len(expected_audiences) == 1
                    else None
                )
            )
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid credentials.")

        settings = app_state.settings
        jwks_cache = app_state.jwks_cache
        if not settings or not jwks_cache:
            raise RuntimeError("Settings or JWKs cache not initialized")

        # First try standard JWT verification
        client_id, exception = await get_client_id_from_token(
            audience, token, settings, jwks_cache
        )

        # If successful, verify the client exists in the database
        if client_id and not exception:
            client = await ClientService.get_client_in_db(
                session, None, client_id
            )
            if not client:
                raise HTTPException(
                    status_code=401, detail="Invalid credentials."
                )
            return client.id

        # If standard auth failed and external auth is allowed, try that next
        if allow_external_auth and settings.enable_external_auth:
            token_response, ext_exception = await verify_external_auth_token(
                token, settings
            )

            if token_response and not ext_exception:
                # Store in context for other parts of the request to access
                context.external_user_info = token_response.user_info
                context.is_external_auth = True

                # Return a special identifier for external auth
                return "external"

        # If we get here, all verification methods failed
        raise HTTPException(
            status_code=getattr(exception, "status_code", 401),
            detail=getattr(exception, "detail", "Invalid credentials."),
        ) from exception

    return dependency


def get_external_user_info() -> Callable[
    [HTTPAuthorizationCredentials],
    Coroutine[Any, Any, Dict[str, Any]],
]:
    """Verify an external token and return user info.

    Returns
    -------
    Callable[[HTTPAuthorizationCredentials],
    Coroutine[Any, Any, Dict[str, Any]]]
        The dependency.
    """

    async def dependency(
        credentials: Annotated[
            HTTPAuthorizationCredentials, Security(bearer_scheme)
        ],
        context: RequestContext = Depends(get_request_context),
        settings: Settings = Depends(get_settings),
    ) -> Dict[str, Any]:
        """Verify an external token and return user info.

        Parameters
        ----------
        credentials : HTTPAuthorizationCredentials
            The authorization credentials.
        context : RequestContext
            The request context.
        settings : Settings
            The application settings.

        Returns
        -------
        Dict[str, Any]
            User information from the external token.

        Raises
        ------
        HTTPException
            If the token is invalid.
        """
        token = credentials.credentials
        scheme = credentials.scheme

        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401, detail="Invalid authentication scheme."
            )

        # Try external verification
        token_response, exception = await verify_external_auth_token(
            token, settings
        )

        if exception or not token_response:
            raise HTTPException(
                status_code=getattr(exception, "status_code", 401),
                detail=getattr(exception, "detail", "Invalid external token."),
            ) from exception

        # Store in context for other parts of the request to access
        context.external_user_info = token_response.user_info
        context.is_external_auth = True

        return token_response.user_info

    return dependency


def get_user_info() -> Callable[
    [RequestContext],
    Coroutine[Any, Any, Dict[str, Any]],
]:
    """Get user info from the request context.

    Returns
    -------
    Callable[[RequestContext], Coroutine[Any, Any, Dict[str, Any]]]
        The dependency.
    """

    async def dependency(
        context: RequestContext = Depends(get_request_context),
    ) -> Dict[str, Any]:
        """Get user info from the request context.

        Parameters
        ----------
        context : RequestContext
            The request context.

        Returns
        -------
        Dict[str, Any]
            User information.

        Raises
        ------
        HTTPException
            If no user info is available.
        """
        if not context.external_user_info:
            raise HTTPException(
                status_code=401,
                detail="No external user information available.",
            )
        return context.external_user_info

    return dependency


def get_jwks_cache() -> JWKSCache:
    """Get the JWKS cache.

    Returns
    -------
    JWKSCache
        The JWKS cache.

    Raises
    ------
    RuntimeError
        If the JWKS cache is not initialized.
    """
    if not app_state.jwks_cache:
        raise RuntimeError("JWKS cache not initialized")
    return app_state.jwks_cache


def get_settings() -> "Settings":
    """Get the application settings.

    Returns
    -------
    Settings
        The application settings.

    Raises
    ------
    RuntimeError
        If the settings are not initialized.
    """
    if not app_state.settings:
        raise RuntimeError("Settings not initialized")
    return app_state.settings


def get_storage() -> Storage:
    """Get the storage backend.

    Returns
    -------
    Storage
        The storage backend.

    Raises
    ------
    RuntimeError
        If the storage backend is not initialized.
    """
    if not app_state.storage_backend:
        raise RuntimeError("Storage backend not initialized")
    return get_storage_backend(app_state.storage_backend)
