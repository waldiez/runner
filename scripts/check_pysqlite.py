# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Check if pysqlite3 is installed and if not, install it."""

import os
import tempfile

# pylint: disable=duplicate-code
# also in ./pre-start.py
# we also have it here to use it in Containerfile.dev
from waldiez.utils.pysqlite3_checker import (
    check_pysqlite3,
    download_sqlite_amalgamation,
    install_pysqlite3,
)


def try_check_pysqlite3() -> None:
    """Check if pysqlite3 is installed and if not, install it.

    Before waldiez tries:
     if on linux and arm64, pysqlite3-binary is not available
    and we need to install it manually.
    """
    cwd = os.getcwd()
    tmp_dir = tempfile.gettempdir()
    os.chdir(tmp_dir)
    try:
        check_pysqlite3()
    except BaseException:  # pylint: disable=broad-exception-caught
        download_path = download_sqlite_amalgamation()
        install_pysqlite3(download_path)
    finally:
        os.chdir(cwd)
    check_pysqlite3()


if __name__ == "__main__":
    try_check_pysqlite3()
