# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Authentication related configuration.

Environment variables (with prefix WALDIEZ_RUNNER_)
---------------------------------------------------
USE_LOCAL_AUTH (bool) # default: True
LOCAL_CLIENT_ID (str) # default: REPLACE_ME/auto-generated
LOCAL_CLIENT_SECRET (str) # default: REPLACE_ME/auto-generated
USE_OIDC_AUTH (bool) # default: False
OIDC_ISSUER_URL (str) # default: None
OIDC_JWKS_URL (str) # default: None
OIDC_AUDIENCE (str) # default: None
OIDC_JWKS_CACHE_TTL (int) # default: 900

Command line arguments (no prefix)
----------------------------------
--use-local-auth|--no-use-local-auth (bool)
--local-client-id (str)
--local-client-secret (str)
--use-oidc-auth|--no-use-oidc-auth (bool)
--oidc-issuer-url (str)
--oidc-jwks-url (str)
--oidc-audience (str)
--oidc-jwks-cache-ttl (int)
"""
# LOCAL_CLIENT_ID=
# USE_LOCAL_AUTH=true
# LOCAL_CLIENT_SECRET=
# USE_OIDC_AUTH=true
# OIDC_ISSUER_URL=
# OIDC_JWKS_URL=
# OIDC_AUDIENCE=
# OIDC_JWKS_CACHE_TTL=

from ._common import get_value


def get_use_local_auth() -> bool:
    """Get whether to use local authentication.

    Returns
    -------
    bool
        Whether to use local authentication
    """
    return get_value("--use-local-auth", "USE_LOCAL_AUTH", bool, True)


def get_local_client_id() -> str:
    """Get the local client ID.

    Returns
    -------
    str
        The local client ID
    """
    return get_value("--local-client-id", "LOCAL_CLIENT_ID", str, "REPLACE_ME")


def get_local_client_secret() -> str:
    """Get the local client secret.

    Returns
    -------
    str
        The local client secret
    """
    return get_value(
        "--local-client-secret", "LOCAL_CLIENT_SECRET", str, "REPLACE_ME"
    )


def get_use_oidc_auth() -> bool:
    """Get whether to use OIDC authentication.

    Returns
    -------
    bool
        Whether to use OIDC authentication
    """
    return get_value("--use-oidc-auth", "USE_OIDC_AUTH", bool, False)


def get_oidc_issuer_url() -> str | None:
    """Get the OIDC issuer URL.

    Returns
    -------
    str | None
        The OIDC issuer URL
    """
    value = get_value("--oidc-issuer-url", "OIDC_ISSUER_URL", str, None)
    if not value:  # skip empty strings
        return None
    return value


def get_oidc_audience() -> str | None:
    """Get the OIDC audience.

    Returns
    -------
    str | None
        The OIDC audience
    """
    value = get_value("--oidc-audience", "OIDC_AUDIENCE", str, None)
    if not value:  # also skip empty strings
        return None
    return value


def get_oidc_jwks_url() -> str | None:
    """Get the OIDC JWKS URL.

    Returns
    -------
    str | None
        The OIDC JWKS URL
    """
    value = get_value("--oidc-jwks-url", "OIDC_JWKS_URL", str, None)
    if not value:  # also skip empty strings
        return None
    return value


def get_oidc_jwks_cache_ttl() -> int:
    """Get the OIDC JWKS cache TTL.

    Returns
    -------
    int
        The OIDC JWKS cache TTL
    """
    return get_value("--oidc-jwks-cache-ttl", "OIDC_JWKS_CACHE_TTL", int, 900)
