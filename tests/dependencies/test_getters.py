# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Test the getters dependencies."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from waldiez_runner.dependencies.context import RequestContext
from waldiez_runner.dependencies.database import DatabaseManager
from waldiez_runner.dependencies.getters import (
    get_admin_client_id,
    get_client_id,
    get_user_info,
)
from waldiez_runner.services.external_token_service import ExternalTokenService


@pytest.mark.asyncio
@patch("waldiez_runner.dependencies.getters.get_client_id_from_token")
@patch("waldiez_runner.dependencies.getters.verify_external_auth_token")
async def test_get_client_id_with_standard_jwt(
    mock_verify_external: AsyncMock, mock_get_client_id: AsyncMock
) -> None:
    """Test get_client_id with standard JWT token.

    Parameters
    ----------
    mock_verify_external : AsyncMock
        Mock for the verify_external_auth_token function
    mock_get_client_id : AsyncMock
        Mock for the get_client_id_from_token function
    """
    # Setup
    mock_get_client_id.return_value = ("client123", "tasks-api", None)
    mock_client = MagicMock()
    mock_client.id = "client123"
    mock_client_service = AsyncMock()
    mock_client_service.get_client_in_db.return_value = mock_client

    with patch(
        "waldiez_runner.dependencies.getters.ClientService", mock_client_service
    ):
        # Create the dependency function
        dependency_fn = get_client_id("tasks-api", allow_external_auth=True)

        # Create needed parameters
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="jwt-token"
        )

        # Mock app_state
        mock_app_state = MagicMock()
        mock_app_state.settings = MagicMock()
        mock_app_state.jwks_cache = MagicMock()

        with patch(
            "waldiez_runner.dependencies.getters.app_state", mock_app_state
        ):
            # Test
            result = await dependency_fn(credentials, MagicMock(), MagicMock())

            # Assertions
            assert result == "client123"
            mock_get_client_id.assert_awaited_once()
            mock_verify_external.assert_not_awaited()


@pytest.mark.asyncio
@patch("waldiez_runner.dependencies.getters.get_client_id_from_token")
@patch("waldiez_runner.dependencies.getters.verify_external_auth_token")
async def test_get_client_id_with_external_token(
    mock_verify_external: AsyncMock, mock_get_client_id: AsyncMock
) -> None:
    """Test get_client_id with external token when JWT fails.

    Parameters
    ----------
    mock_verify_external : AsyncMock
        Mock for the verify_external_auth_token function
    mock_get_client_id : AsyncMock
        Mock for the get_client_id_from_token function
    """
    # Setup - JWT validation fails
    mock_get_client_id.return_value = (None, None, Exception("Invalid JWT"))

    # External validation succeeds
    mock_verify_external.return_value = (
        ExternalTokenService.ExternalTokenResponse(
            valid=True,
            user_info={"id": "ext-user", "name": "External User"},
            id="ext-user",
        ),
        None,
    )

    mock_client_service = AsyncMock()
    mock_client_service.get_client_in_db.return_value = None

    with patch(
        "waldiez_runner.dependencies.getters.ClientService", mock_client_service
    ):
        # Create needed parameters
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="external-token"
        )

        # Mock app_state
        mock_app_state = MagicMock()
        mock_app_state.settings = MagicMock()
        mock_app_state.settings.enable_external_auth = True
        mock_app_state.jwks_cache = MagicMock()

        with patch(
            "waldiez_runner.dependencies.getters.app_state", mock_app_state
        ):
            dependency_fn = get_client_id("tasks-api", allow_external_auth=True)

            original_dependency = dependency_fn

            # mypy: disable-error-code="call-arg"
            async def patched_dependency(
                creds: HTTPAuthorizationCredentials,
                db_manager: DatabaseManager,
                context: RequestContext,
            ) -> str:
                """Call the original dependency with credentials.

                Parameters
                ----------
                creds : HTTPAuthorizationCredentials
                    The authorization credentials to pass
                    to the original dependency
                db_manager : DatabaseManager
                    The database session manager
                context : RequestContext
                    The request context.

                Returns
                -------
                str
                    The client ID returned by the original dependency
                """
                return await original_dependency(
                    creds,
                    db_manager,
                    context,
                )

            # Replace the function temporarily
            dependency_fn = patched_dependency

            # Test
            result = await dependency_fn(credentials, MagicMock(), MagicMock())

            # Assertions
            assert result
            mock_get_client_id.assert_awaited_once()
            mock_verify_external.assert_awaited_once()


@pytest.mark.asyncio
@patch("waldiez_runner.dependencies.getters.get_client_id_from_token")
@patch("waldiez_runner.dependencies.getters.verify_external_auth_token")
async def test_get_client_id_both_auth_methods_fail(
    mock_verify_external: AsyncMock, mock_get_client_id: AsyncMock
) -> None:
    """Test get_client_id when both JWT and external auth fail.

    Parameters
    ----------
    mock_verify_external : AsyncMock
        Mock for the verify_external_auth_token function
    mock_get_client_id : AsyncMock
        Mock for the get_client_id_from_token function
    """
    # Setup - JWT validation fails
    jwt_exception = Exception("Invalid JWT")
    mock_get_client_id.return_value = (None, None, jwt_exception)

    # External validation also fails
    ext_exception = HTTPException(
        status_code=401, detail="Invalid external token"
    )
    mock_verify_external.return_value = (None, ext_exception)

    with patch(
        "waldiez_runner.dependencies.getters.ClientService", AsyncMock()
    ):
        # Create the dependency function
        dependency_fn = get_client_id("tasks-api", allow_external_auth=True)

        # Create needed parameters
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="bad-token"
        )

        # Mock app_state
        mock_app_state = MagicMock()
        mock_app_state.settings = MagicMock()
        mock_app_state.settings.enable_external_auth = True
        mock_app_state.jwks_cache = MagicMock()

        with patch(
            "waldiez_runner.dependencies.getters.app_state", mock_app_state
        ):
            # Test - Should raise exception
            with pytest.raises(HTTPException) as excinfo:
                await dependency_fn(credentials, MagicMock(), MagicMock())

            # Assertions
            assert excinfo.value.status_code == 401
            mock_get_client_id.assert_awaited_once()
            mock_verify_external.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_user_info_with_context_data() -> None:
    """Test get_user_info when context already has user info."""
    # Setup
    context = RequestContext()
    context.external_user_info = {"id": "user123", "role": "admin"}
    context.is_external_auth = True

    # Create the dependency function
    dependency_fn = get_user_info()

    # Test
    result = await dependency_fn(context)

    # Assertions
    assert result == {"id": "user123", "role": "admin"}


@pytest.mark.asyncio
async def test_get_user_info_no_data_required() -> None:
    """Test get_user_info when no user info is available but required=True."""
    # Setup
    context = RequestContext()

    # Create the dependency function (default required=True)
    dependency_fn = get_user_info()

    # Test - Should raise exception
    with pytest.raises(HTTPException) as excinfo:
        await dependency_fn(context)

    # Assertions
    assert excinfo.value.status_code == 401
    assert "No external user information available" in str(excinfo.value.detail)


@pytest.mark.asyncio
@patch("waldiez_runner.dependencies.getters.get_client_id_from_token")
@patch("waldiez_runner.dependencies.getters.verify_external_auth_token")
async def test_get_admin_client_id_with_standard_jwt(
    mock_verify_external: AsyncMock, mock_get_client_id: AsyncMock
) -> None:
    """Test get_admin_client_id with standard JWT token.

    Parameters
    ----------
    mock_verify_external : AsyncMock
        Mock for the verify_external_auth_token function
    mock_get_client_id : AsyncMock
        Mock for the get_client_id_from_token function
    """
    # Setup
    mock_get_client_id.return_value = ("client123", "admin-api", None)
    mock_client = MagicMock()
    mock_client.id = "client123"
    mock_client_service = AsyncMock()
    mock_client_service.get_client_in_db.return_value = mock_client

    with patch(
        "waldiez_runner.dependencies.getters.ClientService", mock_client_service
    ):
        # Create the dependency function
        dependency_fn = get_admin_client_id(
            "admin-api", allow_external_auth=True
        )

        # Create needed parameters
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="jwt-token"
        )

        # Mock app_state
        mock_app_state = MagicMock()
        mock_app_state.settings = MagicMock()
        mock_app_state.settings.enable_external_auth = True
        mock_app_state.jwks_cache = MagicMock()

        with patch(
            "waldiez_runner.dependencies.getters.app_state", mock_app_state
        ):
            # Test
            result = await dependency_fn(credentials, MagicMock(), MagicMock())

            # Assertions
            assert result == "client123"
            mock_get_client_id.assert_awaited_once()
            mock_verify_external.assert_not_awaited()


@pytest.mark.asyncio
@patch("waldiez_runner.dependencies.getters.get_client_id_from_token")
@patch("waldiez_runner.dependencies.getters.verify_external_auth_token")
async def test_get_admin_client_id_with_external_auth_admin(
    mock_verify_external: AsyncMock, mock_get_client_id: AsyncMock
) -> None:
    """Test get_admin_client_id with external auth for admin user.

    Parameters
    ----------
    mock_verify_external : AsyncMock
        Mock for the verify_external_auth_token function
    mock_get_client_id : AsyncMock
        Mock for the get_client_id_from_token function
    """
    # Setup
    mock_get_client_id.return_value = (None, None, Exception("Invalid token"))
    mock_token_response = MagicMock()
    mock_token_response.user_info = {"id": "user123", "isAdmin": True}
    mock_verify_external.return_value = (mock_token_response, None)

    # Create the dependency function
    dependency_fn = get_admin_client_id("admin-api", allow_external_auth=True)

    # Create needed parameters
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="external-token"
    )

    # Mock app_state
    mock_app_state = MagicMock()
    mock_app_state.settings = MagicMock()
    mock_app_state.settings.enable_external_auth = True
    mock_app_state.jwks_cache = MagicMock()

    with patch("waldiez_runner.dependencies.getters.app_state", mock_app_state):
        # Test
        result = await dependency_fn(credentials, MagicMock(), MagicMock())

        # Assertions
        assert result == "user123"
        mock_get_client_id.assert_awaited_once()
        mock_verify_external.assert_awaited_once()


@pytest.mark.asyncio
@patch("waldiez_runner.dependencies.getters.get_client_id_from_token")
@patch("waldiez_runner.dependencies.getters.verify_external_auth_token")
async def test_get_admin_client_id_with_external_auth_non_admin(
    mock_verify_external: AsyncMock, mock_get_client_id: AsyncMock
) -> None:
    """Test get_admin_client_id with external auth for non-admin user.

    Parameters
    ----------
    mock_verify_external : AsyncMock
        Mock for the verify_external_auth_token function
    mock_get_client_id : AsyncMock
        Mock for the get_client_id_from_token function
    """
    # Setup
    mock_get_client_id.return_value = (None, None, Exception("Invalid token"))
    mock_token_response = MagicMock()
    mock_token_response.user_info = {"id": "user123", "isAdmin": False}
    mock_verify_external.return_value = (mock_token_response, None)

    # Create the dependency function
    dependency_fn = get_admin_client_id("admin-api", allow_external_auth=True)

    # Create needed parameters
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="external-token"
    )

    # Mock app_state
    mock_app_state = MagicMock()
    mock_app_state.settings = MagicMock()
    mock_app_state.settings.enable_external_auth = True
    mock_app_state.jwks_cache = MagicMock()

    with patch("waldiez_runner.dependencies.getters.app_state", mock_app_state):
        # Test - Should raise exception for non-admin
        with pytest.raises(HTTPException) as excinfo:
            await dependency_fn(credentials, MagicMock(), MagicMock())

        # Assertions
        assert excinfo.value.status_code == 403
        assert "Admin access required" in str(excinfo.value.detail)
        mock_get_client_id.assert_awaited_once()
        mock_verify_external.assert_awaited_once()


@pytest.mark.asyncio
@patch("waldiez_runner.dependencies.getters.get_client_id_from_token")
@patch("waldiez_runner.dependencies.getters.verify_external_auth_token")
async def test_get_admin_client_id_with_external_auth_admin_isadmin_field(
    mock_verify_external: AsyncMock, mock_get_client_id: AsyncMock
) -> None:
    """Test get_admin_client_id with external auth using 'isAdmin' field.

    Parameters
    ----------
    mock_verify_external : AsyncMock
        Mock for the verify_external_auth_token function
    mock_get_client_id : AsyncMock
        Mock for the get_client_id_from_token function
    """
    # Setup
    mock_get_client_id.return_value = (None, None, Exception("Invalid token"))
    mock_token_response = MagicMock()
    mock_token_response.user_info = {"id": "user123", "isAdmin": True}
    mock_verify_external.return_value = (mock_token_response, None)

    # Create the dependency function
    dependency_fn = get_admin_client_id("admin-api", allow_external_auth=True)

    # Create needed parameters
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="external-token"
    )

    # Mock app_state
    mock_app_state = MagicMock()
    mock_app_state.settings = MagicMock()
    mock_app_state.settings.enable_external_auth = True
    mock_app_state.jwks_cache = MagicMock()

    with patch("waldiez_runner.dependencies.getters.app_state", mock_app_state):
        # Test
        result = await dependency_fn(credentials, MagicMock(), MagicMock())

        # Assertions
        assert result == "user123"
        mock_get_client_id.assert_awaited_once()
        mock_verify_external.assert_awaited_once()
        # Assertions
        assert result == "user123"
        mock_get_client_id.assert_awaited_once()
        mock_verify_external.assert_awaited_once()
