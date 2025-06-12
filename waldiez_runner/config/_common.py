# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Common configuration constants and functions."""

import os
import sys
from pathlib import Path
from typing import Callable, Optional, TypeVar

from dotenv import load_dotenv

ENV_PREFIX = "WALDIEZ_RUNNER_"
ROOT_DIR = Path(__file__).parent.parent.parent.resolve()
DOT_ENV_PATH = ROOT_DIR / ".env"
if DOT_ENV_PATH.exists():
    load_dotenv(DOT_ENV_PATH, override=True)


TRUTHY = ("true", "1", "yes", "y", "on")
FALSY = ("false", "0", "no", "n", "off")
T = TypeVar("T")


def in_container() -> bool:  # pragma: no cover
    """Check if the app is running in a container.

    Returns
    -------
    bool
        Whether the app is running in a container
    """
    # pylint: disable=broad-exception-caught
    try:
        return os.path.isfile("/.dockerenv") or os.path.isfile(
            "/run/.containerenv"
        )
    except Exception:  # pragma: no cover
        return False


def is_testing() -> bool:
    """Check if the app is in testing mode.
    Returns
    -------
    bool
        Whether the app is in testing mode
    """
    return (
        os.environ.get(f"{ENV_PREFIX}TESTING", "False").lower()
        in (
            "1",
            "true",
            "yes",
            "on",
        )
        or "pytest" in sys.argv
    )


def to_kebab(value: str) -> str:
    """Convert a string to kebab case.

    Parameters
    ----------
    value : str
        The string to convert

    Returns
    -------
    str
        The converted string
    """
    return value.replace("_", "-")


def get_value(
    cli_key: str,
    env_key: str,
    cast: Callable[[str], T],
    fallback: T,
    skip_prefix: bool = False,
) -> T:
    """Get a value from CLI args, env vars, or fallback, with type casting.

    Parameters
    ----------
    cli_key : str
        The CLI argument key
    env_key : str
        The environment variable key
    cast : Callable[[str], T]
        The casting function
    fallback : T
        The fallback value
    skip_prefix : bool, optional
        Whether to skip the prefix for the env var, by default False
    Returns
    -------
    T
        The value
    """
    value_str: Optional[str] = None
    env_var = f"{ENV_PREFIX}{env_key}" if not skip_prefix else env_key

    # Handle --key and --no-key for boolean
    if cast is bool:
        return _get_bool(cli_key, env_key, fallback)  # type: ignore

    # Check CLI arg
    if cli_key in sys.argv:
        cli_index = sys.argv.index(cli_key) + 1
        if cli_index < len(sys.argv):
            value_str = sys.argv[cli_index]

    # Check env var
    if not value_str:
        from_env = os.environ.get(env_var)
        if from_env:
            value_str = from_env

    # Try casting if we got a value
    # pylint: disable=too-many-try-statements
    if value_str:
        try:
            casted = cast(value_str)
            if cast is str and not casted:  # pragma: no cover
                return fallback
            # os.environ[env_var] = str(casted)
            return casted
        except (ValueError, TypeError):
            pass

    # os.environ[env_var] = str(fallback)
    # Return fallback
    return fallback


def _get_bool(
    cli_key: str,
    env_key: str,
    fallback: bool,
) -> bool:
    """Get a boolean value from CLI args, env vars, or fallback.

    Parameters
    ----------
    cli_key : str
        The CLI argument key
    env_key : str
        The environment variable key
    fallback : bool
        The fallback value

    Returns
    -------
    bool
        The value
    """
    stripped_key = cli_key.lstrip("-")
    if f"--no-{stripped_key}" in sys.argv:
        # os.environ[f"{ENV_PREFIX}{env_key}"] = "False"
        return False
    if f"--{stripped_key}" in sys.argv:
        # os.environ[f"{ENV_PREFIX}{env_key}"] = "True"
        return True
    from_env = os.environ.get(f"{ENV_PREFIX}{env_key}", str(fallback))
    is_truthy = from_env.lower() not in FALSY
    # os.environ[f"{ENV_PREFIX}{env_key}"] = str(is_truthy)
    return is_truthy


def get_enable_external_auth() -> bool:
    """Get whether to enable external authentication.

    Returns
    -------
    bool
        Whether to enable external authentication
    """
    return get_value(
        "--enable-external-auth", "ENABLE_EXTERNAL_AUTH", bool, False
    )


def get_external_auth_verify_url() -> str:
    """Get the external auth verification URL.

    Returns
    -------
    str
        The external auth verification URL
    """
    return get_value(
        "--external-auth-verify-url",
        "EXTERNAL_AUTH_VERIFY_URL",
        str,
        "https://example.com/verify",
    )


def get_external_auth_secret() -> str:
    """Get the external auth verification secret.

    Returns
    -------
    str
        The external auth verification secret
    """
    return get_value("--external-auth-secret", "EXTERNAL_AUTH_SECRET", str, "")
