# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Server related configuration.

Environment variables (with prefix WALDIEZ_RUNNER_)
---------------------------------------------------
DOMAIN_NAME (str) # default: localhost
HOST (str) # default: localhost
PORT (int) # default: 8000
SECRET_KEY (str) # default: REPLACE_ME / auto-generated
MAX_JOBS (int) # default: 3
FORCE_SSL (bool) # default: True
TRUSTED_HOSTS (str, comma separated) # default: DOMAIN_NAME
TRUSTED_ORIGINS (str, comma separated) # default: https://DOMAIN_NAME
TRUSTED_ORIGIN_REGEX (str) # default: None

Command line arguments (no prefix)
----------------------------------
--domain-name (str)
--host (str)
--port (int)
--secret-key (str)
--max-jobs (int)
--force-ssl (bool)
--trusted-hosts (str, comma separated)
--trusted-origins (str, comma separated)
--trusted-origin-regex (str)
"""

import os
import sys
from typing import List, Optional

from typing_extensions import TypedDict

from ._common import ENV_PREFIX, get_value, in_container


class ServerStatus(TypedDict):
    """Server status type."""

    healthy: bool
    active_tasks: int
    pending_tasks: int
    max_capacity: int
    cpu_count: int | None
    cpu_percent: float
    total_memory: int
    used_memory: int
    memory_percent: float


def get_trusted_hosts(domain_name: str, host: str) -> List[str]:
    """Get the trusted hosts.

    Parameters
    ----------
    domain_name : str
        The domain name

    host : str
        The host to listen on

    Returns
    -------
    List[str]
        The trusted hosts
    """
    from_env = os.environ.get(f"{ENV_PREFIX}TRUSTED_HOSTS", "")
    trusted_hosts = (
        [item for item in from_env.split(",") if item] if from_env else []
    )
    domain_is_not_included = domain_name not in trusted_hosts
    if not trusted_hosts or domain_is_not_included:  # pragma: no branch
        trusted_hosts.append(domain_name)
    if (
        host
        and host not in trusted_hosts
        and host not in ["localhost", "0.0.0.0"]
    ):  # pragma: no branch
        trusted_hosts.append(host)
    if "--trusted-hosts" in sys.argv:  # pragma: no branch
        trusted_host_index = sys.argv.index("--trusted-hosts") + 1
        if trusted_host_index < len(sys.argv):
            trusted_hosts_arg = sys.argv[trusted_host_index]
            if trusted_hosts_arg:  # pragma: no branch
                trusted_hosts_split = trusted_hosts_arg.split(",")
                for trusted_host in trusted_hosts_split:  # pragma: no branch
                    if (
                        trusted_host and trusted_host not in trusted_hosts
                    ):  # pragma: no branch
                        trusted_hosts.append(trusted_host)
    return [host for host in trusted_hosts if host]


def get_trusted_origins(
    domain_name: str, port: int, force_ssl: bool, host: str
) -> List[str]:
    """Get the trusted origins.

    Parameters
    ----------
    domain_name : str
        The domain name
    port : int
        The port
    force_ssl : bool
        Whether to force SSL
    host : str
        The host to listen on

    Returns
    -------
    List[str]
        The trusted origins
    """
    from_env = os.environ.get(f"{ENV_PREFIX}TRUSTED_ORIGINS", "")
    trusted_origins = from_env.split(",") if from_env else []

    default_trusted_origins = [f"https://{domain_name}"]
    if host != domain_name:  # pragma: no branch
        default_trusted_origins.append(f"https://{host}")
    if not force_ssl:
        default_trusted_origins.extend(
            [
                f"http://{domain_name}",
                f"http://{domain_name}:{port}",
                f"http://{host}",
                f"http://{host}:{port}",
            ]
        )

    trusted_origins.extend(
        origin
        for origin in default_trusted_origins
        if origin not in trusted_origins
    )

    if "--trusted-origins" in sys.argv:  # pragma: no branch
        trusted_origin_index = sys.argv.index("--trusted-origins") + 1
        if trusted_origin_index < len(sys.argv):
            trusted_origin = sys.argv[trusted_origin_index]
            if (
                trusted_origin and trusted_origin not in trusted_origins
            ):  # pragma: no branch
                trusted_origins.append(trusted_origin)

    return [origin for origin in trusted_origins if origin]


def get_trusted_origin_regex() -> Optional[str]:
    """Get the trusted origin regex.

    Returns
    -------
    Optional[str]
        The trusted origin regex
    """
    value = get_value(
        "--trusted-origin-regex", "TRUSTED_ORIGIN_REGEX", str, None
    )
    if not value:
        os.environ[f"{ENV_PREFIX}TRUSTED_ORIGIN_REGEX"] = ""
        value = None
    return value


def get_force_ssl() -> bool:
    """Get whether to force SSL.

    Returns
    -------
    bool
        Whether to force SSL
    """
    return get_value("--force-ssl", "FORCE_SSL", bool, True)


def get_default_domain_name() -> str:
    """Get the default domain name.

    Returns
    -------
    str
        The default domain name
    """
    return get_value("--domain-name", "DOMAIN_NAME", str, "localhost")


def get_default_host() -> str:
    """Get the default host.

    Returns
    -------
    str
        The default host
    """
    default = "localhost" if not in_container() else "0.0.0.0"
    return get_value("--host", "HOST", str, default)
    # from_env = os.environ.get(f"{ENV_PREFIX}HOST", default)
    # return from_env if from_env else default


def get_default_port() -> int:
    """Get the default port.

    Returns
    -------
    int
        The default port
    """
    return get_value("--port", "PORT", int, 8000)


def get_secret_key() -> str:
    """Get the secret key.

    Returns
    -------
    str
        The secret key
    """
    value = get_value("--secret-key", "SECRET_KEY", str, "REPLACE_ME")
    return value


def get_max_jobs() -> int:
    """Get the maximum number of jobs.

    Returns
    -------
    int
        The maximum number of jobs
    """
    return get_value("--max-jobs", "MAX_JOBS", int, 3)
