# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Try to download the latest openapi.json and move it to the docs folder."""

import json
import os
import shutil
import sys
import time
from multiprocessing import Process
from pathlib import Path

import urllib3

HTTP = urllib3.PoolManager()

HAD_TO_MODIFY_SYS_PATH = False
ROOT_DIR = Path(__file__).parent.parent.resolve()

try:
    from scripts._lib import (
        ensure_not_running,
        start_services,
        wait_for_services,
    )
except ImportError:
    HAD_TO_MODIFY_SYS_PATH = True
    sys.path.insert(0, str(ROOT_DIR))
    from scripts._lib import (
        ensure_not_running,
        start_services,
        wait_for_services,
    )

# from scripts.test import ensure_not_running, start_services, wait_for_services

PORT = os.environ.get("WALDIEZ_RUNNER_PORT", "8000")
DEST = ROOT_DIR / "docs" / "openapi.json"
OPENAPI_URL = f"http://localhost:{PORT}/openapi.json"


def download_openapi_json() -> bool:
    """Download the OpenAPI JSON file from the server.

    Returns
    ------
    bool
        True if the download was successful, False otherwise.
    """
    # pylint: disable=too-many-try-statements
    try:
        print(f"Trying to download {OPENAPI_URL}")
        DEST.unlink(missing_ok=True)
        with (
            HTTP.request(
                method="GET",
                url=OPENAPI_URL,
                preload_content=False,
                timeout=10,
            ) as response,
            open(DEST, "wb") as out,
        ):
            shutil.copyfileobj(response, out)
        response.release_conn()
        # let's check that it is a json
        with open(DEST, "r", encoding="utf-8") as f_in:
            data = json.loads(f_in.read())
        with open(DEST, "w", encoding="utf-8", newline="\n") as f_out:
            f_out.write(f"{json.dumps(data)}\n")
        print(f"openapi.json downloaded to: {DEST}")
        return True
    except BaseException as e:  # pylint: disable=broad-exception-caught
        print(f"Failed to fetch OpenAPI: {e}")
        return False


def start_dev() -> None:
    """Start the services."""
    make_proc = start_services(silently=True)
    make_proc.wait()


def main() -> None:
    """Main function to download the OpenAPI spec.

    This function checks if the OpenAPI spec is already available in the
    specified destination. If not, it starts a temporary dev server,
    waits for it to be ready, and then attempts to download the OpenAPI
    spec. If the download is successful, it stops the dev server.
    """
    print("Checking if server is already up...")
    if download_openapi_json():
        return
    print("Starting dev server temporarily...")
    ensure_not_running("uvicorn")
    background_sub_proc = Process(target=start_dev, daemon=True)
    background_sub_proc.start()
    wait_for_services()
    all_good = False
    # pylint: disable=too-many-try-statements
    try:
        wait_for_services()
        if download_openapi_json():
            print("Retrieved OpenAPI after starting server.")
            all_good = True
        else:
            print("Failed to download OpenAPI after starting server.")
    finally:
        print("Stopping temporary dev server...")
        background_sub_proc.join(timeout=1)
        ensure_not_running("uvicorn")
        if not all_good:
            sys.exit(1)


if __name__ == "__main__":
    main()
