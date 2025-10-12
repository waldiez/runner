# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pyright: reportUnnecessaryIsInstance=false,reportUnreachable=false

"""Environment variable validation and parsing."""

import json
import re

from fastapi import HTTPException

MAX_ENV_VARS_JSON_SIZE = 5000  # 5KB limit
MAX_ENV_VARS_COUNT = 30  # Max 30 variables
MAX_ENV_KEY_LENGTH = 50  # Max key length
MAX_ENV_VALUE_LENGTH = 500  # Max value length
SAFE_ENV_KEY_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$", re.IGNORECASE)
UNSAFE_ENV_VALUE_PATTERNS = [
    re.compile(r"[;&|`$(){}]"),  # Shell metacharacters
    re.compile(r"\.\.[\\/]"),  # Path traversal
    re.compile(r"\\x[0-9a-fA-F]{2}"),  # Hex encoding
    re.compile(r"%[0-9a-fA-F]{2}"),  # URL encoding
    re.compile(r"https?://"),  # URLs
    re.compile(r"ftp://"),  # FTP URLs
]
PROTECTED_ENV_VARS = {
    # System paths and libraries
    "PATH",
    "LD_LIBRARY_PATH",
    "DYLD_LIBRARY_PATH",
    "PYTHONPATH",
    "LD_PRELOAD",
    "LD_AUDIT",
    "MALLOC_CHECK_",
    # User and system information
    "HOME",
    "USER",
    "USERNAME",
    "LOGNAME",
    "SHELL",
    "TERM",
    "PWD",
    # Network and proxy settings
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "FTP_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "ftp_proxy",
    "all_proxy",
    "no_proxy",
    # Temporary and working directories
    "TMPDIR",
    "TMP",
    "TEMP",
    "TEMPDIR",
    # Python-specific dangerous variables
    "PYTHONSTARTUP",
    "PYTHONEXECUTABLE",
    "PYTHONHOME",
    # Process and debugging
    "PYTHONDEBUG",
    "PYTHONINSPECT",
    "PYTHONOPTIMIZE",
}


# pylint: disable=too-complex
def get_env_vars(  # noqa: C901
    env_vars: str | None,
) -> dict[str, str]:
    """Get environment variables from a JSON string.

    Parameters
    ----------
    env_vars : Optional[str]
        The JSON string of environment variables.

    Returns
    -------
    dict[str, Any]
        The environment variables as a dictionary.

    Raises
    ------
    HTTPException
        If the JSON string is invalid.
    """
    if not env_vars:
        return {}
    environment_vars: dict[str, str] = {}
    if len(env_vars) > MAX_ENV_VARS_JSON_SIZE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"env_vars JSON string exceeds {MAX_ENV_VARS_JSON_SIZE} bytes"
            ),
        )
    try:
        environment_vars = json.loads(env_vars)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400, detail="Invalid JSON format for env_vars"
        ) from e
    if not isinstance(environment_vars, dict):
        raise HTTPException(
            status_code=400, detail="env_vars must be a JSON object"
        )
    if len(environment_vars) > MAX_ENV_VARS_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"env_vars JSON object exceeds {MAX_ENV_VARS_COUNT} items",
        )
    for key, value in environment_vars.items():
        if str(key).upper() in PROTECTED_ENV_VARS:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot override protected system variable: {key}",
            )
        if len(str(key)) > MAX_ENV_KEY_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"env_vars key '{key}' "
                    f"exceeds {MAX_ENV_KEY_LENGTH} characters"
                ),
            )
        if len(str(value)) > MAX_ENV_VALUE_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"env_vars value for key '{key}' "
                    f"exceeds {MAX_ENV_VALUE_LENGTH} characters"
                ),
            )
        if not SAFE_ENV_KEY_PATTERN.match(str(key)):
            raise HTTPException(
                status_code=400,
                detail=f"env_vars key '{key}' contains unsafe characters",
            )
        if any(
            pattern.search(str(value)) for pattern in UNSAFE_ENV_VALUE_PATTERNS
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"env_vars value for key '{key}' contains unsafe characters"
                ),
            )
    return {str(k): str(v) for k, v in environment_vars.items()}
