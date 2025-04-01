# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-return-doc,missing-yield-doc
# pylint: disable=too-few-public-methods,protected-access
"""Test waldiez_runner.dependencies.auth.decoding*."""

from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import jwt.algorithms
import pytest

from waldiez_runner.dependencies.auth import decode_local_jwt, decode_oidc_jwt


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
