# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Utility functions for the dependencies module."""

import socket
from contextlib import closing


# noinspection PyBroadException
def is_port_available(port: int) -> bool:
    """Check if the port is available.

    Parameters
    ----------
    port : int
        Port number

    Returns
    -------
    bool
        True if port is available
    """
    # Check IPv4
    try:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.bind(("", port))
    except BaseException:  # pylint: disable=broad-exception-caught
        return False

    # Check IPv6
    try:  # pragma: no cover
        with closing(
            socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        ) as sock:
            # Disable dual-stack to only check IPv6
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            sock.bind(("", port))
    except BaseException:  # pylint: disable=broad-exception-caught
        return False

    return True


def get_available_port() -> int:
    """Get an available port.

    Returns
    -------
    int
        An available port number
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as soc:
        soc.bind(("", 0))
        soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return soc.getsockname()[1]
