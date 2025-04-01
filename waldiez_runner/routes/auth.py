# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Authentication routes."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List

import jwt
from fastapi import APIRouter, Depends, Form, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from waldiez_runner.config import Settings
from waldiez_runner.dependencies import get_db, get_settings
from waldiez_runner.services import ClientService

router = APIRouter()
ACCESS_TOKEN_EXPIRY = timedelta(minutes=60)
REFRESH_TOKEN_EXPIRY = timedelta(hours=24)

LOG = logging.getLogger(__name__)


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str
    audience: str | List[str] | None = None


class TokensResponse(BaseModel):
    """Token response."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime
    refresh_expires_at: datetime
    audience: str


@router.post("/token/", include_in_schema=False)
@router.post(
    "/token",
    response_model=TokensResponse,
    summary="Get a token for local authentication.",
    description=(
        "Get a token for local authentication "
        "(only valid if local authentication is enabled)."
    ),
)
async def get_token(
    client_id: str = Form(
        ...,
        examples=[""],  # just to avoid the default in swagger
    ),
    client_secret: str = Form(..., examples=[""]),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokensResponse:
    """Get a token for local authentication.

    Parameters
    ----------
    client_id : str
        The client ID.
    client_secret : str
        The client secret.
    session: AsyncSession
        The database session.
    settings : Settings
        The settings instance.

    Returns
    -------
    TokensResponse
        The token response.

    Raises
    ------
    HTTPException
        If the credentials are invalid.
    """
    if not settings.use_local_auth:  # pragma: no cover
        raise HTTPException(
            status_code=400, detail="Token issuance is disabled in OIDC mode."
        )
    client = await ClientService.verify_client(
        session, client_id, client_secret
    )

    if not client:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    return generate_tokens(client_id, client.audience, settings)


@router.post("/token/refresh/", include_in_schema=False)
@router.post(
    "/token/refresh",
    response_model=TokensResponse,
    summary="Refresh a token.",
    description="Refresh a token.",
)
async def refresh_a_token(
    data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokensResponse:
    """Refresh a token.

    Parameters
    ----------
    data : RefreshTokenRequest
        The refresh token request.
    session: AsyncSession
        The database session.
    settings : Settings
        The settings instance.
    Returns
    -------
    TokensResponse
        The token response.

    Raises
    ------
    HTTPException
        If the refresh token is invalid.
    """
    if not settings.use_local_auth:  # pragma: no cover
        raise HTTPException(
            status_code=400,
            detail="Token issuance is disabled in OIDC mode.",
        )
    # pylint: disable=too-many-try-statements
    try:
        payload = jwt.decode(
            data.refresh_token,
            settings.secret_key.get_secret_value(),
            algorithms=["HS256"],
            issuer=settings.domain_name,
            audience=data.audience,
            options={"verify_aud": False} if not data.audience else None,
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Invalid token type")

        client_id = payload["sub"]
        audience = payload["aud"]
    except jwt.PyJWKError as exc:
        LOG.debug("Invalid token: %s", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid token payload"
        ) from exc
    except BaseException as exc:
        if isinstance(exc, jwt.ExpiredSignatureError):
            LOG.debug("Expired token: %s", exc)
            raise HTTPException(
                status_code=401, detail="Expired refresh token"
            ) from exc
        if isinstance(exc, jwt.InvalidTokenError):
            LOG.debug("Invalid token: %s", exc)
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        LOG.error("Internal server error: %s", exc)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from exc
    await validate_client(session, client_id, audience)
    return generate_tokens(client_id, audience, settings)


async def validate_client(
    session: AsyncSession, client_id: str, audience: str
) -> None:
    """Validate the client.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    client_id : str
        The client ID.
    audience : str
        The token audience.

    Raises
    ------
    HTTPException
        If the client is invalid, deleted, or has the token has wrong audience.
    """
    client = await ClientService.get_client_in_db(session, None, client_id)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid client")
    if client.deleted_at:
        raise HTTPException(status_code=401, detail="Client is deleted")
    if client.audience != audience:
        raise HTTPException(status_code=401, detail="Invalid audience")


def generate_tokens(
    client_id: str,
    audience: str,
    settings: Settings,
) -> TokensResponse:
    """Generate access and refresh tokens.

    Parameters
    ----------
    client_id : str
        The client ID.
    audience : str
        The audience.
    settings : Settings
        The settings instance.

    Returns
    -------
    TokensResponse
        The token response.
    """
    now = datetime.now(timezone.utc)
    access_expires_at = now + ACCESS_TOKEN_EXPIRY
    refresh_expires_at = now + REFRESH_TOKEN_EXPIRY

    access_payload = {
        "sub": client_id,
        "aud": audience,
        "exp": access_expires_at,
        "iss": settings.domain_name,
        "type": "access",
    }

    refresh_payload = {
        "sub": client_id,
        "aud": audience,
        "exp": refresh_expires_at,
        "iss": settings.domain_name,
        "type": "refresh",
    }

    secret_key = settings.secret_key.get_secret_value()
    access_token = jwt.encode(
        access_payload,
        secret_key,
        algorithm="HS256",
    )
    refresh_token = jwt.encode(
        refresh_payload,
        secret_key,
        algorithm="HS256",
    )

    return TokensResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",  # nosemgrep # nosec
        expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
        audience=audience,
    )
