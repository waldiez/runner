# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Try to download the latest openapi.json and move it to the docs folder."""

import os
import sys
import threading
import time
from pathlib import Path

import httpx

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
        response = httpx.get(OPENAPI_URL, timeout=5)
        response.raise_for_status()
        response_text = response.text
        if not response_text.endswith("\n"):
            response_text += "\n"
        DEST.write_text(response_text, encoding="utf-8")
        print(f"openapi.json downloaded to: {DEST}")
        return True
    except httpx.RequestError as e:
        print(f"Failed to fetch OpenAPI: {e}")
        return False


def main() -> None:
    """Main function to download the OpenAPI spec.

    This function checks if the OpenAPI spec is already available in the
    specified destination. If not, it starts a temporary dev server,
    waits for it to be ready, and then attempts to download the OpenAPI
    spec. If the download is successful, it stops the dev server.
    """
    print("Checking if OpenAPI spec is already available...")
    if download_openapi_json():
        return

    print("Starting dev server temporarily...")
    ensure_not_running("uvicorn")
    make_proc = start_services(silently=True)
    time.sleep(5)
    background_sub_proc = threading.Thread(target=make_proc.wait, daemon=True)
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
        make_proc.kill()
        background_sub_proc.join(timeout=1)
        sys.exit(0 if all_good else 1)


if __name__ == "__main__":
    main()
