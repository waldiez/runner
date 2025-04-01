# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=consider-using-with

"""Run tests for the waldiez_runner package."""

import os
import shutil
import subprocess  # nosemgrep # nosec
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import httpx

ROOT_DIR = Path(__file__).parent.parent
os.environ["PYTHONUNBUFFERED"] = "1"


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


def before_tests() -> None:
    """Run before the tests."""
    ensure_test_requirements()
    db_path = ROOT_DIR / "waldiez_runner_test.db"
    if db_path.exists():
        db_path.unlink()
    # let's also back any .env file if it exists
    env_file = ROOT_DIR / ".env"
    if env_file.exists():
        shutil.copy(env_file, ROOT_DIR / ".env.before_tests")


def run_pytest() -> None:
    """Run pytest."""
    coverage_dir = ROOT_DIR / "coverage" / "backend"
    if coverage_dir.exists():
        shutil.rmtree(coverage_dir)
    coverage_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(  # nosemgrep # nosec
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "pyproject.toml",
            "-n",
            "0",
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
        ],
        check=True,
        cwd=ROOT_DIR,
    )


def after_tests() -> None:
    """Run after the tests."""
    db_path = ROOT_DIR / "waldiez_runner_test.db"
    if db_path.exists():
        db_path.unlink()
    # let's restore the .env file if it was backed up
    env_file = ROOT_DIR / ".env"
    env_file_before_tests = ROOT_DIR / ".env.before_tests"
    if env_file.exists():
        env_file.unlink()
    if env_file_before_tests.exists():
        shutil.copy(env_file_before_tests, env_file)
        env_file_before_tests.unlink()


def wait_for_services() -> None:
    """Wait for the services to be ready.

    Raises
    ------
    RuntimeError
        If the services are not ready after
        10 retries.
    """
    # a simple loop to call the /health endpoint of the server
    # if it fails, sleep (exponential backoff) and retry
    server_port = os.environ.get("WALDIEZ_RUNNER_PORT", "8000")
    retries = 0
    while retries < 10:
        # pylint: disable=too-many-try-statements
        try:
            response = httpx.get(f"http://localhost:{server_port}/health")
            response.raise_for_status()
            print("Services are ready: ", response.text)
            return
        except httpx.HTTPError as e:
            print(
                f"Services are not ready, error: {e} attempt: {retries + 1}/10"
            )
            retries += 1
            time.sleep(2**retries)
    raise RuntimeError("Services are not ready")


def _try_stop_on_windows(service_name: str) -> None:
    """Try to stop a service on Windows.

    Parameters
    ----------
    service_name : str
        The name of the service to stop
    """
    partial_cmd = shutil.which(service_name) or service_name
    cwd = ROOT_DIR
    powershell_cmd = (
        f'powershell -NoProfile -Command "'
        f"Get-CimInstance Win32_Process | "
        f"Where-Object {{$_.CommandLine -like '*{partial_cmd}*'}} | "
        f"ForEach-Object {{Stop-Process -Id $_.ProcessId -Force}}"
        '"'
    )
    try:
        subprocess.run(powershell_cmd, shell=True, check=False, cwd=cwd)
    except BaseException:  # pylint: disable=broad-exception-caught
        pass


def ensure_not_running(service_name: str) -> None:
    """Ensure the service is not running.

    Parameters
    ----------
    service_name : str
        The name of the service to stop

    Raises
    ------
    subprocess.CalledProcessError
        If an error occurs while stopping the service.
    """
    if os.name == "nt":
        _try_stop_on_windows(service_name)
        return
    kill_cmd = "kill -9"
    ps_aux = "ps aux"
    grep = f"grep {service_name}"
    skip_grep = "grep -v grep"
    awk_print = "awk '{print $2}'"
    output_redirection_or_ok = "> /dev/null 2>&1 || true"
    inner_cmd = f"{ps_aux} | {grep} | {skip_grep} | {awk_print} | xargs"
    cmd_to_run = f"{kill_cmd} $({inner_cmd}) {output_redirection_or_ok}"
    try:
        subprocess.run(  # nosemgrep # nosec
            cmd_to_run,
            shell=True,
            check=False,
            cwd=ROOT_DIR,
        )
    except subprocess.CalledProcessError as error:
        print(f"Error while stopping {service_name}: {error}")
        raise


def in_container() -> bool:
    """Check if the script is running in a container.

    Returns
    -------
    bool
        Whether the script is running in a container.
    """
    return os.path.isfile("/.dockerenv") or os.path.isfile("/run/.containerenv")


def check_make_cmd() -> bool:
    """Check if 'make' is available. Attempt to install if missing

    Returns
    -------
    bool
        Whether 'make' is available or not
    """
    if is_make_available():
        return True

    if install_make_for_platform():
        return is_make_available()

    print("Could not ensure 'make' is installed.")
    return False


def is_make_available() -> bool:
    """Check if 'make' is available on the system.

    Returns
    -------
    bool
        Whether 'make' is available or not.
    """
    return shutil.which("make") is not None


def try_run(cmd: List[str]) -> bool:
    """Run a command safely and return True if successful.

    Parameters
    ----------
    cmd : List[str]
        The command to run.

    Returns
    -------
    bool
        Whether the command was successful.
    """
    try:
        subprocess.run(cmd, check=True)
        return True
    except BaseException as e:  # pylint: disable=broad-exception-caught
        cmd_str = " ".join(cmd)
        print(f"{cmd_str} command failed:: {e}")
        return False


def install_make_for_platform() -> bool:
    """Try to install 'make' based on the OS/distro.

    Returns
    -------
    bool
        Whether 'make' was successfully installed.
    """
    if sys.platform == "darwin":
        return install_make_mac()
    if sys.platform == "win32":
        return install_make_windows()
    if sys.platform.startswith("linux"):
        return install_make_linux()
    return False


def install_make_mac() -> bool:
    """Install make on macOS using Homebrew.

    Returns
    -------
    bool
        Whether make was successfully
        installed
    """
    if shutil.which("brew"):
        return try_run(["brew", "install", "make"])
    print("Homebrew not found.")
    return False


def install_make_windows() -> bool:
    """Install make on Windows using Chocolatey or MSYS2.

    Returns
    -------
    bool
        Whether make was successfully
        installed
    """
    choco = shutil.which("choco")
    if choco:
        return try_run(["choco", "install", "make", "-y"])

    pacman = shutil.which("pacman")
    if pacman and "msys" in pacman.lower():
        return try_run(["pacman", "-Sy", "--noconfirm", "make"])

    print("Could not find a package manager on Windows.")
    return False


def install_make_linux() -> bool:
    """Install make on Debian, RPM, or Arch-based Linux systems.

    Returns
    -------
    bool
        Whether make was successfully
        installed
    """
    if is_debian_based():
        return try_run(["sudo", "apt", "update"]) and try_run(
            ["sudo", "apt", "install", "-y", "make"]
        )

    if is_rpm_based():
        if shutil.which("dnf"):
            return try_run(["sudo", "dnf", "install", "-y", "make"])
        if shutil.which("yum"):
            return try_run(["sudo", "yum", "install", "-y", "make"])

    if is_arch_based():
        return try_run(["sudo", "pacman", "-Sy", "--noconfirm", "make"])

    print("Unsupported Linux distribution.")
    return False


def is_debian_based() -> bool:
    """Check if the system is Debian-based.

    Returns
    -------
    bool
        Whether the system is Debian-based or not
    """
    if os.path.isfile("/etc/debian_version"):
        return True
    os_release = read_os_release()
    return "debian" in os_release.get("ID_LIKE", "")


def is_rpm_based() -> bool:
    """Check if the system is RPM-based.

    Returns
    -------
    bool
        Whether the system is RPM-based or not.
    """
    if os.path.isfile("/etc/redhat-release"):
        return True
    os_release = read_os_release()
    return any(
        keyword in os_release.get("ID_LIKE", "")
        for keyword in ("rhel", "fedora")
    )


def is_arch_based() -> bool:
    """Check if the system is Arch-based.

    Returns
    -------
    bool
        Whether the system is Arch-based or not.
    """
    if os.path.isfile("/etc/arch-release"):
        return True
    os_release = read_os_release()
    if "arch" in os_release.get("ID_LIKE", ""):
        return True
    pacman_path = shutil.which("pacman")
    return pacman_path is not None and "msys" not in pacman_path.lower()


@lru_cache(maxsize=1)
def read_os_release() -> Dict[str, str]:
    """Parse /etc/os-release into a dict.

    Returns
    -------
    Dict[str, str]
        The key-value pairs from the
        /etc/os-release file.
    """
    result = {}
    # pylint: disable=too-many-try-statements
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    result[k] = v.strip('"')
    except FileNotFoundError:
        pass
    return result


def drop_db_data() -> None:
    """Drop everything in the database."""
    # scripts/drop.py --force
    drop_proc = subprocess.Popen(  # nosemgrep # nosec
        [sys.executable, "scripts/drop.py", "--force"],
        cwd=ROOT_DIR,
    )
    drop_proc.wait()


def start_services(silently: bool = True) -> subprocess.Popen[Any]:
    """Start the services, optionally suppressing all output.

    Parameters
    ----------
    silently : bool, optional
        Whether to suppress the output, by default True
    Returns
    -------
    subprocess.Popen
        The process that starts the services.
    """
    make_target = "dev-no-reload"
    if not in_container():
        make_target += "-local"
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        start_proc = subprocess.Popen(  # nosemgrep # nosec
            ["make", make_target],
            stdout=devnull if silently else None,
            stderr=devnull if silently else None,
            shell=False,
            cwd=ROOT_DIR,
            env=os.environ,
        )
        return start_proc


def run_smoke_tests() -> None:
    """Run the smoke tests."""
    # best to be used in a devcontainer
    # the env vars must be already set
    # a real redis server must be running (fakeredis seems to not be enough)
    # if in devcontainer, we are ok regarding redis
    # the db could be sqlite, but if in devcontainer, we can use postgres
    # one process (background) to start the services
    # and one to call "scripts/smoke.py" (but after the services are started)
    if check_make_cmd() is False:
        print("make is not available")
        return
    ensure_not_running("taskiq")
    ensure_not_running("uvicorn")
    drop_db_data()

    make_proc = start_services("--debug" not in sys.argv)
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
    before_tests()
    run_pytest()
    after_tests()


if __name__ == "__main__":
    main()
