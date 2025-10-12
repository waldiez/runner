# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""App dependency getters."""

from collections.abc import AsyncGenerator, Coroutine
from typing import Any, Callable

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing_extensions import Annotated

from waldiez_runner.config import Settings
from waldiez_runner.services.client_service import ClientService

from .auth import (
    ADMIN_API_AUDIENCE,
    TASK_API_AUDIENCE,
    get_client_id_from_token,
    verify_external_auth_token,
)
from .context import RequestContext, get_request_context
from .database import DatabaseManager
from .jwks import JWKSCache
from .lifecycle import app_state
from .storage import Storage, get_storage_backend

bearer_scheme = HTTPBearer()


async def get_db_manager() -> AsyncGenerator[DatabaseManager, None]:
    """Get the database session.

    Yields
    ------
    DatabaseManager
        The database manager.

    Raises
    ------
    RuntimeError
        If the database is not initialized.
    """
    if not app_state.db or not app_state.db.engine:
        raise RuntimeError("Database not initialized")
    yield app_state.db


# pylint: disable=line-too-long
def get_client_id(
    *expected_audiences: str, allow_external_auth: bool = True
) -> Callable[
    [HTTPAuthorizationCredentials, DatabaseManager, RequestContext],
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
    Callable[[HTTPAuthorizationCredentials, DatabaseManager, RequestContext],
    Coroutine[Any, Any, str]]
        The dependency.
    """

    async def dependency(
        credentials: Annotated[
            HTTPAuthorizationCredentials, Security(bearer_scheme)
        ],
        db_manager: Annotated[DatabaseManager, Depends(get_db_manager)],
        context: Annotated[RequestContext, Depends(get_request_context)],
    ) -> str:
        """Check the audience of the JWT payload.

        Parameters
        ----------
        credentials : HTTPAuthorizationCredentials
            The authorization credentials.
        db_manager : DatabaseManager
            The database session manager.
        context : RequestContext
            The request context.

        Returns
        -------
        str
            The subject of the JWT or the token itself for external tokens.

        Raises
        ------
        HTTPException
            If the audience is not as expected.
        RuntimeError
            If the settings or JWKs cache are not initialized.
        """
        token = credentials.credentials
        scheme = credentials.scheme
        audience: str | list[str] | None = None
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
        client_id, _, exception = await get_client_id_from_token(
            audience, token, settings, jwks_cache
        )

        # If successful, verify the client exists in the database
        if client_id and not exception:
            async with db_manager.session() as session:
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
                sub = token_response.user_info.get(
                    "sub",
                    token_response.user_info.get("id", token),
                )
                return sub if isinstance(sub, str) else token

        # If we get here, all verification methods failed
        raise HTTPException(
            status_code=getattr(exception, "status_code", 401),
            detail=getattr(exception, "detail", "Invalid credentials."),
        ) from exception

    return dependency


def get_client_id_with_admin_check(
    allow_external_auth: bool = True,
) -> Callable[
    [HTTPAuthorizationCredentials, DatabaseManager, RequestContext],
    Coroutine[Any, Any, tuple[str, bool]],
]:
    """Require a client ID and return whether the user is admin.

    This accepts both TASK_API_AUDIENCE and ADMIN_API_AUDIENCE.

    Parameters
    ----------
    allow_external_auth : bool, optional
        Whether to allow external authentication, by default True

    Returns
    -------
    Callable[[HTTPAuthorizationCredentials, DatabaseManager, RequestContext],
    Coroutine[Any, Any,tuple[str, bool]]]
        The dependency that returns (client_id, is_admin).
    """

    # pylint: disable=too-many-locals
    async def dependency(
        credentials: Annotated[
            HTTPAuthorizationCredentials, Security(bearer_scheme)
        ],
        db_manager: Annotated[DatabaseManager, Depends(get_db_manager)],
        context: Annotated[RequestContext, Depends(get_request_context)],
    ) -> tuple[str, bool]:
        """Check the audience and return client_id with admin status.

        Parameters
        ----------
        credentials : HTTPAuthorizationCredentials
            The authorization credentials.
        db_manager : DatabaseManager
            The database session manager.
        context : RequestContext
            The request context.

        Returns
        -------
        tuple[str, bool]
            The client_id and whether the user is admin.

        Raises
        ------
        HTTPException
            If the audience is not as expected.
        RuntimeError
            If the settings or JWKs cache are not initialized.
        """
        token = credentials.credentials
        scheme = credentials.scheme
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid credentials.")

        settings = app_state.settings
        jwks_cache = app_state.jwks_cache
        if not settings or not jwks_cache:
            raise RuntimeError("Settings or JWKs cache not initialized")

        # Accept both task and admin audiences
        expected_audiences = [TASK_API_AUDIENCE, ADMIN_API_AUDIENCE]

        # First try standard JWT verification
        client_id, token_audience, exception = await get_client_id_from_token(
            expected_audiences, token, settings, jwks_cache
        )

        # If successful, verify the client exists in the database
        if client_id and not exception:
            async with db_manager.session() as session:
                client = await ClientService.get_client_in_db(
                    session, None, client_id
                )
            if not client:
                raise HTTPException(
                    status_code=401, detail="Invalid credentials."
                )
            is_admin = token_audience == ADMIN_API_AUDIENCE
            return client.id, is_admin

        # If standard auth failed and external auth is allowed, try that next
        if allow_external_auth and settings.enable_external_auth:
            token_response, ext_exception = await verify_external_auth_token(
                token, settings
            )

            if token_response and not ext_exception:
                # Store in context for other parts of the request to access
                context.external_user_info = token_response.user_info
                context.is_external_auth = True

                # Check if user is admin
                is_admin = token_response.user_info.get("isAdmin", False)

                # Return a special identifier for external auth
                sub = token_response.user_info.get(
                    "sub", token_response.user_info.get("id", token)
                )
                client_id = sub if isinstance(sub, str) else token
                return client_id, is_admin

        # If we get here, all verification methods failed
        raise HTTPException(
            status_code=getattr(exception, "status_code", 401),
            detail=getattr(exception, "detail", "Invalid credentials."),
        ) from exception

    return dependency


# Module-level dependency for unified client ID and admin check
get_client_id_with_admin = get_client_id_with_admin_check()


def get_admin_client_id(
    *expected_audiences: str, allow_external_auth: bool = True
) -> Callable[
    [HTTPAuthorizationCredentials, DatabaseManager, RequestContext],
    Coroutine[Any, Any, str],
]:
    """Require a specific audience for the request and check admin role
    for external auth.

    Parameters
    ----------
    *expected_audiences : str
        The expected audiences.
    allow_external_auth : bool, optional
        Whether to allow external authentication, by default True

    Returns
    -------
    Callable[[HTTPAuthorizationCredentials, DatabaseManager, RequestContext],
    Coroutine[Any, Any, str]]
        The dependency.
    """

    # pylint: disable=too-many-locals
    async def dependency(
        credentials: Annotated[
            HTTPAuthorizationCredentials, Security(bearer_scheme)
        ],
        db_manager: Annotated[DatabaseManager, Depends(get_db_manager)],
        context: Annotated[RequestContext, Depends(get_request_context)],
    ) -> str:
        """Check the audience of the JWT payload and admin role
        for external auth.

        Parameters
        ----------
        credentials : HTTPAuthorizationCredentials
            The authorization credentials.
        db_manager : DatabaseManager
            The database session manager.
        context : RequestContext
            The request context.

        Returns
        -------
        str
            The subject of the JWT or the token itself for external tokens.

        Raises
        ------
        HTTPException
            If the audience is not as expected or user is not admin.
        RuntimeError
            If the settings or JWKs cache are not initialized.
        """
        token = credentials.credentials
        scheme = credentials.scheme
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid credentials.")

        settings = app_state.settings
        jwks_cache = app_state.jwks_cache
        if not settings or not jwks_cache:
            raise RuntimeError("Settings or JWKs cache not initialized")

        audience: str | list[str] | None = None
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

        # First try standard JWT verification
        client_id, _, exception = await get_client_id_from_token(
            audience, token, settings, jwks_cache
        )

        # If successful, verify the client exists in the database
        if client_id and not exception:
            async with db_manager.session() as session:
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
                # Check if user is admin
                user_info = token_response.user_info
                is_admin = user_info.get("isAdmin", False)
                if not is_admin:
                    raise HTTPException(
                        status_code=403, detail="Admin access required."
                    )

                # Store in context for other parts of the request to access
                context.external_user_info = user_info
                context.is_external_auth = True

                # Return a special identifier for external auth
                sub = user_info.get(
                    "sub",
                    user_info.get("id", token),
                )
                return sub if isinstance(sub, str) else token

        # If we get here, all verification methods failed
        raise HTTPException(
            status_code=getattr(exception, "status_code", 401),
            detail=getattr(exception, "detail", "Invalid credentials."),
        ) from exception

    return dependency


def get_external_user_info() -> Callable[
    [HTTPAuthorizationCredentials, RequestContext, Settings],
    Coroutine[Any, Any, dict[str, Any]],
]:
    """Verify an external token and return user info.

    Returns
    -------
    Callable[[HTTPAuthorizationCredentials, RequestContext, Settings],
    Coroutine[Any, Any, Dict[str, Any]]]
        The dependency.
    """

    async def dependency(
        credentials: Annotated[
            HTTPAuthorizationCredentials, Security(bearer_scheme)
        ],
        context: Annotated[RequestContext, Depends(get_request_context)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, Any]:
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
        dict[str, Any]
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
    Coroutine[Any, Any, dict[str, Any]],
]:
    """Get user info from the request context.

    Returns
    -------
    Callable[[RequestContext], Coroutine[Any, Any, dict[str, Any]]]
        The dependency.
    """

    async def dependency(
        context: Annotated[RequestContext, Depends(get_request_context)],
    ) -> dict[str, Any]:
        """Get user info from the request context.

        Parameters
        ----------
        context : RequestContext
            The request context.

        Returns
        -------
        dict[str, Any]
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
