# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Utility functions for the dependencies module."""

import socket


def is_port_available(port: int) -> bool:
    """Check if a port is available.

    Parameters
    ----------
    port : int
        Port to check.

    Returns
    -------
    bool
        True if the port is available, False otherwise.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as soc:
        result = soc.connect_ex(("localhost", port))
        return result != 0


def get_available_port() -> int:
    """Get an available port.

    Returns
    -------
    int
        The available port.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as soc:
        soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        soc.bind(("", 0))
        return soc.getsockname()[1]
