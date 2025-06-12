# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Authentication related functions for dependencies."""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Tuple

import jwt
import jwt.algorithms
from fastapi import HTTPException

from ..services.external_token_service import ExternalTokenService
from .jwks import JWKSCache

TASK_API_AUDIENCE = "tasks-api"
CLIENT_API_AUDIENCE = "clients-api"


Audience = Literal[
    "tasks-api",
    "clients-api",
]
"""Audiences for the JWT token."""

VALID_AUDIENCES = [TASK_API_AUDIENCE, CLIENT_API_AUDIENCE]


if TYPE_CHECKING:
    from waldiez_runner.config import Settings


LOG = logging.getLogger(__name__)


def decode_local_jwt(
    token: str,
    settings: "Settings",
    audience: str | List[str] | None,
    verify_aud: bool = True,
    leeway: float = 30,
) -> Dict[str, Any]:
    """Decode local HS256 JWT.

    Parameters
    ----------
    token : str
        The JWT token.
    settings : Settings
        The settings instance.
    audience : str | List[str] | None
        The expected audience.
    verify_aud : bool
        Whether to verify the audience.
    leeway : float
        The leeway in seconds.
    Returns
    -------
    Dict[str, Any]
        The decoded payload.
    """
    return jwt.decode(
        token,
        settings.secret_key.get_secret_value(),
        algorithms=["HS256"],
        issuer=settings.domain_name,
        audience=audience,
        options=(
            {"verify_aud": False} if not verify_aud or not audience else None
        ),
        leeway=leeway,
    )


async def decode_oidc_jwt(
    token: str,
    settings: "Settings",
    jwks_cache: JWKSCache,
    verify_aud: bool = True,
    leeway: float = 30,
) -> Dict[str, Any]:
    """Decode OIDC RS256 JWT using cached JWKS.

    Parameters
    ----------
    token : str
        The JWT token.
    settings : Settings
        The settings instance.
    jwks_cache : JWKSCache
        The JWKS cache.
    verify_aud : bool
        Whether to verify the audience.
    leeway : float
        The leeway in seconds.
    Returns
    -------
    Dict[str, Any]
        The decoded payload.

    Raises
    ------
    HTTPException
        If the token is invalid.
    """
    jwks = await jwks_cache.get_keys()
    keys = jwks.get("keys", [])
    if not keys:  # pragma: no cover
        raise HTTPException(status_code=500, detail="No keys found in JWKS.")
    header = jwt.get_unverified_header(token)

    rsa_jwk = None
    rsa_alg = "RS256"
    kid = header.get("kid")
    alg = header.get("alg")
    for key in keys:  # pragma: no branch
        if key.get("kid") == kid:
            rsa_jwk = key
            rsa_alg = key.get("alg", rsa_alg)
            break

    if rsa_jwk is None:
        raise HTTPException(
            status_code=401, detail="Unable to find appropriate key."
        )

    if alg != rsa_alg:  # pragma: no cover
        raise HTTPException(status_code=401, detail="JWT algorithm mismatch.")

    issuer_url = settings.oidc_issuer_url
    if not issuer_url:  # pragma: no cover
        raise HTTPException(
            status_code=500, detail="OIDC issuer URL is not set."
        )
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(rsa_jwk)
    return jwt.decode(
        token,
        public_key,  # type: ignore
        algorithms=[rsa_alg],
        issuer=str(issuer_url),
        audience=settings.oidc_audience,
        leeway=leeway,
        options=(
            {"verify_aud": False}
            if not verify_aud or not settings.oidc_audience
            else None
        ),
    )


async def get_client_id_from_token(
    expected_audience: str | List[str] | None,
    token: str,
    settings: "Settings",
    jwks_cache: JWKSCache,
) -> Tuple[str | None, BaseException | None]:
    """Get the client ID from the token.

    Parameters
    ----------
    expected_audience : str | List[str] | None
        The expected audience.
    token : str
        The token.
    settings : Settings
        The settings instance.
    jwks_cache : JWKSCache
        The JWKS cache.
    Returns
    -------
    Tuple[str, BaseException | None]
        The client ID and the exception if any.
    """
    # pylint: disable=broad-exception-caught, too-many-try-statements
    try:
        if settings.use_local_auth:
            payload = decode_local_jwt(
                token,
                settings,
                audience=expected_audience,
            )
        elif settings.use_oidc_auth:  # pragma: no cover
            payload = await decode_oidc_jwt(
                token,
                settings,
                jwks_cache=jwks_cache,
            )
        else:  # pragma: no cover
            return None, HTTPException(
                status_code=500, detail="Auth configuration error."
            )

        client_id = payload.get("sub")
        if not client_id:
            return None, HTTPException(
                status_code=401, detail="Invalid credentials."
            )
        return client_id, None

    except jwt.PyJWTError as e:
        LOG.error("Error while decoding token: %s", e)
        return None, e
    except HTTPException as e:
        LOG.error("Error while decoding token: %s", e)
        return None, e
    except BaseException as e:
        LOG.error("Error while decoding token: %s", e)
        return None, e


async def verify_external_auth_token(
    token: str,
    settings: "Settings",
) -> Tuple[
    Optional[ExternalTokenService.ExternalTokenResponse],
    Optional[BaseException],
]:
    """Verify an external token.

    Parameters
    ----------
    token : str
        The token to verify
    settings : Settings
        The application settings

    Returns
    -------
    Tuple[Optional[ExternalTokenService.ExternalTokenResponse],
    Optional[BaseException]]
        A tuple containing:
        - The token response object if verification succeeded, None otherwise
        - An exception if verification failed, None otherwise
    """
    if (
        not settings.enable_external_auth
        or not settings.external_auth_verify_url
    ):
        return None, HTTPException(
            status_code=401, detail="External auth not enabled"
        )

    return await ExternalTokenService.verify_external_token(
        token, settings.external_auth_verify_url, settings.external_auth_secret
    )
