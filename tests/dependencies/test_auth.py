# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-return-doc,missing-yield-doc
# pylint: disable=too-few-public-methods,protected-access
# pyright: reportOptionalMemberAccess=false
"""Test authentication dependencies."""

from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from waldiez_runner.config.settings import Settings
from waldiez_runner.dependencies.auth import (
    decode_local_jwt,
    decode_oidc_jwt,
    verify_external_auth_token,
)
from waldiez_runner.services.external_token_service import ExternalTokenResponse


def test_decode_local_jwt_valid() -> None:
    """Test decoding a valid local JWT."""
    token_payload = {
        "sub": "client_123",
        "aud": "tasks-api",
        "iss": "test.local",
    }
    secret_key = "test-secret"  # nosemgrep # nosec
    token = jwt.encode(token_payload, secret_key, algorithm="HS256")

    class MockSettings:
        """Mock Settings class to simulate required settings."""

        secret_key = MagicMock(
            get_secret_value=MagicMock(return_value="test-secret")
        )
        domain_name = "test.local"

    decoded = decode_local_jwt(
        token,
        MockSettings(),  # type: ignore
        audience="tasks-api",
        verify_aud=True,
    )
    assert decoded["sub"] == "client_123"


def test_decode_local_jwt_invalid_audience() -> None:
    """Test decoding a local JWT with an invalid audience."""
    token_payload = {
        "sub": "client_123",
        "aud": "wrong-api",
        "iss": "test.local",
    }
    secret_key = "test-secret"  # nosemgrep # nosec
    token = jwt.encode(token_payload, secret_key, algorithm="HS256")

    class MockSettings:
        """Mock Settings class to simulate required settings."""

        secret_key = MagicMock(
            get_secret_value=MagicMock(return_value="test-secret")
        )
        domain_name = "test.local"

    with pytest.raises(jwt.PyJWTError):
        decode_local_jwt(
            token,
            MockSettings(),  # type: ignore
            audience="tasks-api",
            verify_aud=True,
        )


@pytest.mark.asyncio
async def test_decode_oidc_jwt_valid() -> None:
    """Test decoding a valid OIDC JWT."""
    token = "mocked.jwt.token"  # nosemgrep # nosec
    mock_payload = {"sub": "client_123", "aud": "tasks-api"}

    class MockSettings:
        """Mock Settings class to simulate required settings."""

        oidc_issuer_url = "https://keycloak.local"
        oidc_audience = "tasks-api"

    jwks_cache = AsyncMock()
    jwks_cache.get_keys.return_value = {
        "keys": [{"kid": "test-key", "alg": "RS256"}]
    }

    with (
        patch("jwt.decode", return_value=mock_payload) as mock_decode,
        patch(
            "jwt.get_unverified_header",
            return_value={"kid": "test-key", "alg": "RS256"},
        ),
        patch(
            "jwt.algorithms.RSAAlgorithm.from_jwk",
            return_value={"public_key": "key"},
        ),
    ):
        decoded = await decode_oidc_jwt(
            token,
            MockSettings(),  # type: ignore
            jwks_cache,
        )

    assert decoded == mock_payload
    mock_decode.assert_called_once()


@pytest.mark.asyncio
async def test_decode_oidc_jwt_key_not_found() -> None:
    """Test decoding an OIDC JWT with a key not found."""
    token_payload = {
        "sub": "client_123",
        "aud": "tasks-api",
        "iss": "https://keycloak.local",
        "alg": "RS256",
    }
    token = jwt.encode(
        token_payload,
        "wrong-key",
        algorithm="HS256",
        headers={"kid": "test-key"},
    )

    class MockSettings:
        """Mock Settings class to simulate required settings."""

        oidc_issuer_url = "https://keycloak.local"
        oidc_audience = "tasks-api"

    jwks_cache = AsyncMock()
    jwks_cache.get_keys.return_value = {
        "keys": [{"kid": "wrong", "alg": "HS256"}]
    }
    mock_payload = {"sub": "client_123", "aud": "tasks-api", "alg": "HS256"}
    with (
        patch("jwt.decode", return_value=mock_payload),
        patch("jwt.get_unverified_header", return_value={"kid": "test-key"}),
    ):
        with pytest.raises(Exception, match="Unable to find appropriate key"):
            await decode_oidc_jwt(
                token,
                MockSettings(),  # type: ignore
                jwks_cache,
            )


class MockedSettings(Settings):
    """Mock settings for tests."""

    # Don't declare these fields at class level in Pydantic v2
    # enable_external_auth: bool
    # external_auth_verify_url: str
    # external_auth_secret: str

    @classmethod
    def create_mock(
        cls,
        enable_external_auth: bool = True,
        external_auth_verify_url: str = "https://example.com/verify",
        external_auth_secret: str = "test-secret",  # nosec B107
    ) -> "MockedSettings":
        """Create a mocked settings object."""
        return cls.model_construct(
            enable_external_auth=enable_external_auth,
            external_auth_verify_url=external_auth_verify_url,
            external_auth_secret=external_auth_secret,
        )


@pytest.mark.asyncio
async def test_verify_external_auth_token_disabled() -> None:
    """Test verifying external auth token when disabled."""
    settings = MockedSettings.create_mock(enable_external_auth=False)

    response, exception = await verify_external_auth_token("token", settings)

    assert response is None
    assert isinstance(exception, HTTPException)
    assert exception.status_code == 401
    assert "External auth not enabled" in str(exception.detail)


@pytest.mark.asyncio
async def test_verify_external_auth_token_no_url() -> None:
    """Test verifying external auth token with no URL configured."""
    settings = MockedSettings.create_mock(external_auth_verify_url="")

    response, exception = await verify_external_auth_token("token", settings)

    assert response is None
    assert isinstance(exception, HTTPException)
    assert exception.status_code == 401
    assert "External auth not enabled" in str(exception.detail)


@pytest.mark.asyncio
@patch("waldiez_runner.services.ExternalTokenService.verify_external_token")
async def test_verify_external_auth_token_success(
    mock_verify: AsyncMock,
) -> None:
    """Test successful external auth token verification."""
    settings = MockedSettings.create_mock()
    token_response = ExternalTokenResponse(
        valid=True,
        user_info={"id": "user123", "name": "Test User"},
        id="user123",
    )
    mock_verify.return_value = (token_response, None)

    response, exception = await verify_external_auth_token(
        "test-token", settings
    )

    assert exception is None
    assert response is token_response
    assert response.user_info["id"] == "user123"
    mock_verify.assert_awaited_once_with(
        "test-token", "https://example.com/verify", "test-secret"
    )


@pytest.mark.asyncio
@patch("waldiez_runner.services.ExternalTokenService.verify_external_token")
async def test_verify_external_auth_token_failure(
    mock_verify: AsyncMock,
) -> None:
    """Test failed external auth token verification."""
    settings = MockedSettings.create_mock()
    expected_exception = HTTPException(status_code=401, detail="Invalid token")
    mock_verify.return_value = (None, expected_exception)

    response, exception = await verify_external_auth_token(
        "bad-token", settings
    )

    assert response is None
    assert exception is expected_exception
    mock_verify.assert_awaited_once_with(
        "bad-token", "https://example.com/verify", "test-secret"
    )
