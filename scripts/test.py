# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=consider-using-with,invalid-name
# pyright: reportImplicitRelativeImport=false

"""Run tests for the waldiez_runner package."""

import os
import shutil
import subprocess  # nosemgrep # nosec
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT_DIR = HERE.parent.resolve()

HAD_TO_MODIFY_SYS_PATH = False

try:
    from _lib import (
        check_make_cmd,
        drop_db_data,
        ensure_not_running,
        start_services,
        wait_for_services,
    )
except ImportError:
    HAD_TO_MODIFY_SYS_PATH = True  # pyright: ignore[reportConstantRedefinition]
    sys.path.insert(0, str(HERE))
    from _lib import (  # type: ignore
        check_make_cmd,
        drop_db_data,
        ensure_not_running,
        start_services,
        wait_for_services,
    )


def ensure_test_requirements() -> None:
    """Ensure the test requirements are installed."""
    requirements_file = ROOT_DIR / "requirements" / "test.txt"
    subprocess.run(  # nosemgrep # nosec
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "waldiez",
            "-r",
            str(requirements_file),
        ],
        check=True,
        cwd=ROOT_DIR,
    )


def run_pytest() -> None:
    """Run pytest."""
    coverage_dir = ROOT_DIR / "coverage"
    if coverage_dir.exists():
        shutil.rmtree(coverage_dir)
    coverage_dir.mkdir(parents=True, exist_ok=True)
    n = "0" if sys.platform == "win32" else "auto"
    args = [
        sys.executable,
        "-m",
        "pytest",
        "-c",
        "pyproject.toml",
        "-n",
        f"{n}",
        "--cov=waldiez_runner",
        "--cov-branch",
        "--cov-context=test",
        "--cov-report=term-missing:skip-covered",
        "--cov-report",
        "lcov:coverage/lcov.info",
        "--cov-report",
        "html:coverage/html",
        "--cov-report",
        "xml:coverage/coverage.xml",
        "--junitxml=coverage/xunit.xml",
        "tests",
    ]
    print("Running pytest...\n")
    print(" ".join(args) + "\n")
    subprocess.run(  # nosemgrep # nosec
        args,
        check=True,
        cwd=ROOT_DIR,
    )


def run_smoke_tests() -> None:
    """Run the smoke tests."""
    # best to be used in a devcontainer
    # the env vars must be already set
    # a real redis server must be running (fakeredis seems to not be enough)
    # if in devcontainer, we are ok regarding redis
    # the db could be sqlite, but if in devcontainer, we can use postgres
    # one process (background) to start the services
    # and one to call "scripts/smoke.py" (but after the services are started)
    if not check_make_cmd():
        print("make is not available")
        return
    ensure_not_running("taskiq")
    ensure_not_running("uvicorn")
    drop_db_data()

    make_proc = start_services("--debug" not in sys.argv)
    time.sleep(5)
    background_sub_proc = threading.Thread(target=make_proc.wait, daemon=True)
    background_sub_proc.start()

    wait_for_services()

    smoke_proc = subprocess.Popen(  # nosemgrep # nosec
        [sys.executable, "scripts/smoke.py"],
        cwd=ROOT_DIR,
    )
    smoke_proc.wait()
    make_proc.terminate()
    make_proc.wait()
    background_sub_proc.join()


def main() -> None:
    """Run the tests."""
    if "--smoke" in sys.argv:
        os.environ["WALDIEZ_RUNNER_SMOKE_TESTING"] = "true"
        try:
            run_smoke_tests()
        finally:
            ensure_not_running("taskiq")
            ensure_not_running("uvicorn")
            os.environ.pop("WALDIEZ_RUNNER_SMOKE_TESTING", None)
        return
    run_pytest()


if __name__ == "__main__":
    try:
        main()
    finally:
        if HAD_TO_MODIFY_SYS_PATH:
            sys.path.pop(0)
