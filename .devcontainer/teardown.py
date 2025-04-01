# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Actions to perform when we exit the devcontainer."""

import shutil
from pathlib import Path

HERE = Path(__file__).parent
ROOT_DIR = HERE.parent

GIT_BAK_PATH = ROOT_DIR / ".git.bak"


def main() -> None:
    """Perform checks and actions when we exit the devcontainer."""
    if GIT_BAK_PATH.exists():
        if (ROOT_DIR / ".git").is_dir():
            print("Removing .git directory")
            shutil.rmtree(ROOT_DIR / ".git")
        print("Restoring .git file from .git.bak")
        GIT_BAK_PATH.rename(ROOT_DIR / ".git")


if __name__ == "__main__":
    main()
