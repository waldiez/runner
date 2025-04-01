# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Toggle between containerized and local dev environments."""

import os
from pathlib import Path

ENV_KEY = "WALDIEZ_RUNNER_"
ROOT_DIR = Path(__file__).parent.parent
DOT_ENV_PATH = ROOT_DIR / ".env"

BOOL_KEYS = ["REDIS", "POSTGRES"]
HOST_KEYS = ["REDIS_HOST", "DB_HOST"]


def toggle_env() -> None:
    """Toggle between containerized and local dev environments."""
    if not DOT_ENV_PATH.exists():
        print(f"{DOT_ENV_PATH} does not exist.")
        return
    running_in_container = in_container()
    with open(DOT_ENV_PATH, "r", encoding="utf-8") as f_in:
        lines = f_in.readlines()
    with open(DOT_ENV_PATH, "w", encoding="utf-8", newline="\n") as f_out:
        for line in lines:
            if line.startswith(ENV_KEY):
                key = line.split("=")[0][len(ENV_KEY) :]
                if key in BOOL_KEYS:
                    if running_in_container:
                        line = line.replace("0", "1")
                    else:
                        line = line.replace("1", "0")
                    print(f"Setting {line}")
                elif key in HOST_KEYS:
                    host = key.split("_")[0].lower()
                    if running_in_container:
                        line = line.replace("localhost", host)
                    else:
                        line = line.replace(host, "localhost")
                    print(f"Setting {line}")
            f_out.write(line)


def in_container() -> bool:
    """Check if the script is running in a container.

    Returns
    -------
    bool
        Whether the script is running in a container.
    """
    return os.path.isfile("/.dockerenv") or os.path.isfile("/run/.containerenv")


if __name__ == "__main__":
    toggle_env()
