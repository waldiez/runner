# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Task specific configuration.

Environment variables (with prefix WALDIEZ_RUNNER_)
---------------------------------------------------
INPUT_TIMEOUT (int) # default: 180

Command line arguments (no prefix)
--------------------------------------------------
--input-timeout (int) # default: 180
"""

from ._common import get_value


def get_input_timeout() -> int:
    """Get the input timeout.

    Returns
    -------
    int
        The input timeout
    """
    return get_value("--input-timeout", "INPUT_TIMEOUT", int, 180)
