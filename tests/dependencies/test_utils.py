# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Test waldiez_runner.dependencies._utils.*"""

import socket

# noinspection PyProtectedMember
from waldiez_runner.dependencies._utils import (
    get_available_port,
    is_port_available,
)


def test_is_port_available_free_port() -> None:
    """Test if is_port_available returns True for a free port."""
    port = get_available_port()
    assert is_port_available(port) is True


def test_is_port_available_used_port() -> None:
    """Test if is_port_available returns False for a port in use."""
    # occupy a port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as soc:
        soc.bind(("", 0))
        soc.listen(1)
        used_port = soc.getsockname()[1]

        # While the socket is open, the port should not be available
        assert is_port_available(used_port) is False

    # After closing, the port should be available again
    assert is_port_available(used_port) is True


def test_get_available_port() -> None:
    """Test if get_available_port returns a port that is actually available."""
    port = get_available_port()

    # Ensure the returned port is actually available
    assert is_port_available(port) is True

    # occupy the port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as soc:
        soc.bind(("localhost", port))
        soc.listen(1)
        assert is_port_available(port) is False
