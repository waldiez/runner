# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Postgresql related configuration.

Environment variables (with prefix WALDIEZ_RUNNER_)
---------------------------------------------------
POSTGRES (bool) # default: False
POSTGRES_HOST (str) # default: db if in container else localhost
POSTGRES_PORT (int) # default: 5432
POSTGRES_DB (str) # default: db_name
POSTGRES_USER (str) # default: db_user
POSTGRES_PASSWORD (str) # default: db_password
POSTGRES_URL (str) # default: None (auto-generated)

Command line arguments (no prefix)
----------------------------------
--postgres|--no-postgres (bool)
--postgres-host (str)
--postgres-port (int)
--postgres-db (str)
--postgres-user (str)
--postgres-password (str)
--postgres-url (str)
"""

from ._common import get_value, in_container


def get_postgres_enabled() -> bool:
    """Get whether Postgres is enabled.

    Returns
    -------
    bool
        Whether Postgres is enabled
    """
    return get_value("--postgres", "POSTGRES", bool, False)


def get_db_host() -> str:
    """Get the Postgres host.

    Returns
    -------
    str
        The Postgres host
    """
    fallback = "db" if in_container() else "localhost"
    return get_value("--postgres-host", "POSTGRES_HOST", str, fallback)


def get_db_port() -> int:
    """Get the Postgres port.

    Returns
    -------
    int
        The Postgres port
    """
    return get_value("--postgres-port", "POSTGRES_PORT", int, 5432)


def get_db_name() -> str:
    """Get the Postgres database name.

    Returns
    -------
    str
        The Postgres database name
    """
    return get_value("--postgres-db", "POSTGRES_DB", str, "db_name")


def get_db_user() -> str:
    """Get the Postgres user.

    Returns
    -------
    str
        The Postgres user
    """
    return get_value("--postgres-user", "POSTGRES_USER", str, "db_user")


def get_db_password() -> str:
    """Get the Postgres password.

    Returns
    -------
    str
        The Postgres password
    """
    return get_value(
        "--postgres-password", "POSTGRES_PASSWORD", str, "db_password"
    )


def get_db_url() -> str | None:
    """Get the Postgres URL.

    Returns
    -------
    str | None
        The Postgres URL
    """
    value = get_value("--postgres-url", "POSTGRES_URL", str, None)
    return value if value else None
