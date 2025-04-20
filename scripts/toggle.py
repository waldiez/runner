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
    existing_lines = {}

    # Read existing .env into a dict
    with open(DOT_ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith(ENV_KEY):
                key, _, value = line.strip().partition("=")
                stripped_key = key[len(ENV_KEY) :]
                existing_lines[stripped_key] = value

    updated_lines = {}

    for key in BOOL_KEYS:
        new_val = "1" if use_container else "0"
        updated_lines[key] = new_val
        print(f"Setting {ENV_KEY}{key}={new_val}")

    for key in HOST_KEYS:
        base = key.split("_", maxsplit=1)[0].lower()
        new_val = base if use_container else "localhost"
        updated_lines[key] = new_val
        print(f"Setting {ENV_KEY}{key}={new_val}")

    # Merge existing unrelated lines
    final_lines = []
    with open(DOT_ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith(ENV_KEY):
                key = line.split("=")[0][len(ENV_KEY) :]
                if key in updated_lines:
                    continue  # Will be added below
            final_lines.append(line.rstrip("\n"))

    # Append updated keys
    for key in BOOL_KEYS + HOST_KEYS:
        final_lines.append(f"{ENV_KEY}{key}={updated_lines[key]}")

    # Write everything back
    with open(DOT_ENV_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(final_lines) + "\n")

    print("Environment toggled successfully.")


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
