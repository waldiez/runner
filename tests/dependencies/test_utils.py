# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.
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
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("", 0))
        _, port = sock.getsockname()

        # Port should not be available
        assert is_port_available(port) is False
    finally:
        sock.close()
