# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Toggle between containerized and local dev environments."""

import argparse
import os
from pathlib import Path

ENV_KEY = "WALDIEZ_RUNNER_"
ROOT_DIR = Path(__file__).parent.parent
DOT_ENV_PATH = ROOT_DIR / ".env"

BOOL_KEYS = ["REDIS", "POSTGRES"]
HOST_KEYS = ["REDIS_HOST", "DB_HOST"]


def toggle_env(mode: str) -> None:
    """Toggle between containerized and local dev environments.

    Parameters
    ----------
    mode : str
        The mode to use for toggling. Can be "detect", "local", or "container".
        Defaults to "detect". If "detect", it will check if the script is
        running in a container and toggle accordingly.
        If "local", it will set all container settings to local (no redis or
        postgres). If "container", it will set all local
        settings to container.
    """
    if not DOT_ENV_PATH.exists():
        DOT_ENV_PATH.touch()
    use_container = should_use_container(mode)
    with open(DOT_ENV_PATH, "r", encoding="utf-8") as f_in:
        lines = f_in.readlines()
    with open(DOT_ENV_PATH, "w", encoding="utf-8", newline="\n") as f_out:
        for line in lines:
            if line.startswith(ENV_KEY):
                key = line.split("=")[0][len(ENV_KEY) :]
                if key in BOOL_KEYS:
                    if use_container:
                        line = line.replace("0", "1")
                    else:
                        line = line.replace("1", "0")
                    print(f"Setting {line}")
                elif key in HOST_KEYS:
                    host = key.split("_")[0].lower()
                    if use_container:
                        line = line.replace("localhost", host)
                    else:
                        line = line.replace(host, "localhost")
                    print(f"Setting {line}")
            f_out.write(line)


def should_use_container(mode: str) -> bool:
    """Check if the script should use container settings.

    Parameters
    ----------
    mode : str
        The mode to use for toggling. Can be "detect", "local", or "container".
        Defaults to "detect". If "detect", it will check if the script is
        running in a container and toggle accordingly.
        If "local", it will set all container settings to local (no redis or
        postgres). If "container", it will set all local
        settings to container.

    Returns
    -------
    bool
        Whether the script should use container settings.

    Raises
    ------
    ValueError
        If the mode is not expected

    """
    if mode == "detect":
        return in_container()
    if mode == "local":
        return False
    if mode == "container":
        return True
    raise ValueError(f"Invalid mode: {mode}")


def in_container() -> bool:
    """Check if the script is running in a container.

    Returns
    -------
    bool
        Whether the script is running in a container.
    """
    return os.path.isfile("/.dockerenv") or os.path.isfile("/run/.containerenv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Toggle between containerized and local dev environments."
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["detect", "local", "container"],
        default="detect",
        help=(
            "The mode to use for toggling. "
            "Can be 'detect', 'local', or 'container'. Defaults to 'detect'."
        ),
    )
    args = parser.parse_args()
    toggle_env(args.mode)
