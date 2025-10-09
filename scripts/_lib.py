# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Common functions for the scripts folder."""

import os
import shutil
import subprocess  # nosemgrep # nosec
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).parent.parent
os.environ["PYTHONUNBUFFERED"] = "1"


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
    # pylint: disable=broad-exception-caught
    # noinspection PyBroadException
    try:
        subprocess.run(
            powershell_cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            cwd=cwd,
        )
    except BaseException:
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


def try_run(cmd: list[str]) -> bool:
    """Run a command safely and return True if successful.

    Parameters
    ----------
    cmd : list[str]
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
def read_os_release() -> dict[str, str]:
    """Parse /etc/os-release into a dict.

    Returns
    -------
    dict[str, str]
        The key-value pairs from the
        /etc/os-release file.
    """
    result: dict[str, str] = {}
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
    # pylint: disable=consider-using-with
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
    if silently:
        with open(os.devnull, "w", encoding="utf-8") as devnull:
            start_proc = subprocess.Popen(  # nosemgrep # nosec
                ["make", make_target],
                stdout=devnull,
                stderr=devnull,
                shell=False,
                cwd=ROOT_DIR,
                env=os.environ,
            )
    else:
        # pylint: disable=consider-using-with
        start_proc = subprocess.Popen(  # nosemgrep # nosec
            ["make", make_target],
            shell=False,
            cwd=ROOT_DIR,
            env=os.environ,
        )
    return start_proc
