#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught,too-many-try-statements,
# pylint: disable=missing-function-docstring,missing-param-doc
# pylint: disable=missing-return-doc,missing-yield-doc,missing-raises-doc
"""
deps.py — Detect and (try to) install dependencies:
  - AWS CLI v2
  - rsync

Usage:
  python deps.py
  python deps.py --install-aws
  python deps.py --install-rsync
  python deps.py --dry-run
  python deps.py -v
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Sequence

DRY_RUN = "--dry-run" in sys.argv
VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv


def log(msg: str) -> None:
    print(msg)


def v(msg: str) -> None:
    if VERBOSE:
        print(msg)


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def run(
    cmd: Sequence[str], *, check: bool = True, env: dict[str, Any] | None = None
) -> int:
    cmd_str = " ".join(map(str, cmd))
    if DRY_RUN:
        log(f"[dry-run] {cmd_str}")
        return 0
    v(f"[run] {cmd_str}")
    return subprocess.run(cmd, check=check, env=env).returncode  # nosec


def sudo_prefix() -> list[str]:
    """Return ['sudo'] if needed & available, else []."""
    # Windows doesn't have sudo
    if sys.platform.startswith("win"):
        return []
    # If already root, no sudo
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return []
    # Use sudo when available
    return ["sudo"] if which("sudo") else []


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def is_windows() -> bool:
    return sys.platform.startswith("win")


def cpu_arch() -> str:
    # Normalize architecture names
    m = platform.machine().lower()
    if m in ("x86_64", "amd64"):
        return "x86_64"
    if m in ("aarch64", "arm64"):
        return "aarch64"
    return m


# ---------------------------
# AWS CLI installation
# ---------------------------
def aws_cli_installed() -> bool:
    if not which("aws"):
        return False
    try:
        out = subprocess.check_output(["aws", "--version"])  # nosec
        v(out.decode().strip())
        return True
    except Exception:
        return False


def install_aws_macos() -> None:
    url = "https://awscli.amazonaws.com/AWSCLIV2.pkg"
    # cspell: disable-next-line
    with tempfile.TemporaryDirectory() as tmpd:
        # cspell: disable-next-line
        pkg = Path(tmpd) / "AWSCLIV2.pkg"
        curl = which("curl")
        if curl:
            run([curl, "-L", url, "-o", str(pkg)])
        else:
            # fallback to python download
            urllib.request.urlretrieve(url, pkg)  # nosec
        # cspell: disable-next-line
        # sudo installer -pkg ./AWSCLIV2.pkg -target /
        run([*sudo_prefix(), "installer", "-pkg", str(pkg), "-target", "/"])


def install_aws_linux() -> None:
    arch = cpu_arch()
    if arch == "x86_64":
        url = "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"
    elif arch == "aarch64":
        url = "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip"
    else:
        raise RuntimeError(
            f"Unsupported CPU architecture for AWS CLI v2: {arch}"
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        # cspell: disable-next-line
        zip_path = Path(tmp_dir) / "awscliv2.zip"
        curl = which("curl")
        if curl:
            run([curl, "-L", url, "-o", str(zip_path)])
        else:
            # fallback to python download
            urllib.request.urlretrieve(url, zip_path)  # nosemgrep # nosec

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(zip_path)

        installer = Path(zip_path) / "aws" / "install"
        if not installer.exists():
            raise RuntimeError("AWS CLI installer not found after extraction")

        # try to ensure executable bit
        try:
            run(["chmod", "+x", str(installer)], check=False)
        except Exception:
            pass

        run([*sudo_prefix(), str(installer)])


def install_aws_windows() -> None:
    # Requires admin rights; silent install
    msi_url = "https://awscli.amazonaws.com/AWSCLIV2.msi"
    with tempfile.TemporaryDirectory() as tmp_dir:
        # cspell: disable-next-line
        msi = Path(tmp_dir) / "AWSCLIV2.msi"
        # Use PowerShell to download if curl not available
        curl = which("curl")
        if curl:
            run([curl, "-L", msi_url, "-o", str(msi)])
        else:
            # powershell Invoke-WebRequest
            ps = which("powershell") or "powershell"
            run(
                [
                    ps,
                    "-NoProfile",
                    "-Command",
                    f'Invoke-WebRequest -Uri "{msi_url}" -OutFile "{msi}"',
                ]
            )

        # Install silently
        # cspell: disable-next-line
        run(["msiexec.exe", "/i", str(msi), "/qn"], check=False)


def ensure_aws_cli() -> None:
    if aws_cli_installed():
        log("AWS CLI: already installed")
        return
    log("Installing AWS CLI v2...")
    if is_macos():
        install_aws_macos()
    elif is_linux():
        install_aws_linux()
    elif is_windows():
        install_aws_windows()
    else:
        raise RuntimeError(f"Unsupported OS: {sys.platform}")

    if aws_cli_installed():
        log("AWS CLI: installation complete")
    else:
        log("AWS CLI: installation attempted but not detected on PATH")


# ---------------------------
# rsync installation
# ---------------------------
def rsync_installed() -> bool:
    return which("rsync") is not None


def install_rsync_macos() -> None:
    brew = which("brew")
    if brew:
        run([brew, "install", "rsync"])
        return
    # macOS usually has rsync (older). If not, suggest installing Homebrew.
    raise RuntimeError("Homebrew not found. Install Homebrew or provide rsync.")


def detect_linux_os() -> tuple[str, str]:
    """Return (os_id, pretty_name) from /etc/os-release or similar."""
    os_id = "unknown"
    os_name = "Unknown Linux"
    os_release = Path("/etc/os-release")
    lsb_release = Path("/etc/lsb-release")

    def parse_lines(lines: list[str]) -> dict[str, str]:
        result = {}
        for line in lines:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, val = line.split("=", 1)
            result[key.strip()] = val.strip().strip('"')
        return result

    try:
        if os_release.exists():
            data = parse_lines(
                os_release.read_text(encoding="utf-8").splitlines()
            )
            os_id = data.get("ID", os_id).lower()
            os_name = data.get("PRETTY_NAME", os_name)
        elif lsb_release.exists():
            data = parse_lines(
                lsb_release.read_text(encoding="utf-8").splitlines()
            )
            os_id = data.get("DISTRIB_ID", os_id).lower()
            os_name = data.get("DISTRIB_DESCRIPTION", os_name)
    except Exception:
        pass

    return os_id, os_name


# pylint: disable=too-many-return-statements
def detect_linux_pkg_mgr() -> str | None:
    os_id, os_name = detect_linux_os()
    v(f"Detected OS: {os_name} ({os_id})")

    # Map by distro family
    if os_id in {"ubuntu", "debian", "raspbian"}:
        return "apt" if which("apt") else "apt-get"
    if os_id in {"fedora", "rhel", "centos", "rocky", "almalinux", "ol"}:
        return "dnf" if which("dnf") else "yum"
    if os_id in {"opensuse", "sles"}:
        return "zypper"
    if os_id in {"arch", "manjaro"}:
        return "pacman"
    if os_id in {"alpine"}:
        return "apk"

    # Fallback generic detection (if /etc/os-release not found)
    for mgr in ("apt-get", "apt", "dnf", "yum", "zypper", "pacman", "apk"):
        if which(mgr):
            return mgr
    return None


def install_rsync_linux() -> None:
    mgr = detect_linux_pkg_mgr()
    if not mgr:
        raise RuntimeError("No supported package manager found for rsync.")
    sp = sudo_prefix()
    log(f"Detected package manager: {mgr}")

    if mgr in ("apt", "apt-get"):
        run([*sp, mgr, "update"], check=False)
        run([*sp, mgr, "install", "-y", "rsync"])
    elif mgr == "dnf":
        run([*sp, "dnf", "install", "-y", "rsync"])
    elif mgr == "yum":
        run([*sp, "yum", "install", "-y", "rsync"])
    elif mgr == "zypper":
        run([*sp, "zypper", "--non-interactive", "install", "rsync"])
    elif mgr == "pacman":
        run([*sp, "pacman", "-Sy", "--noconfirm", "rsync"])
    elif mgr == "apk":
        run([*sp, "apk", "add", "rsync"])
    else:
        raise RuntimeError(f"Unsupported package manager: {mgr}")


def install_rsync_windows() -> None:
    choco = which("choco")
    if choco:
        run(["choco", "install", "rsync", "-y"], check=False)
        return
    raise RuntimeError(
        "Chocolatey not found. "
        "Install Chocolatey and run `choco install rsync`, "
        "or install rsync via MSYS2 or cwRsync."
    )


def ensure_rsync() -> None:
    if rsync_installed():
        log("rsync: already installed")
        return
    log("Installing rsync...")
    if is_macos():
        install_rsync_macos()
    elif is_linux():
        install_rsync_linux()
    elif is_windows():
        install_rsync_windows()
    else:
        raise RuntimeError(f"Unsupported OS: {sys.platform}")

    if rsync_installed():
        log("rsync: installation complete")
    else:
        log("rsync: installation attempted but not detected on PATH")


# ---------------------------
# Main
# ---------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Install/verify AWS CLI v2 and rsync."
    )
    p.add_argument(
        "--install-aws", action="store_true", help="Install/verify AWS CLI only"
    )
    p.add_argument(
        "--install-rsync", action="store_true", help="Install/verify rsync only"
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Print actions without executing"
    )
    p.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose output"
    )
    return p.parse_known_args()[0]


def do(do_aws: bool, do_rsync: bool) -> None:
    if do_aws:
        ensure_aws_cli()
    if do_rsync:
        ensure_rsync()
    # Show versions
    if which("aws"):
        try:
            out = subprocess.check_output(["aws", "--version"])  # nosec
            log(f"aws --version: {out.decode().strip()}")
        except Exception:
            pass
    if which("rsync"):
        try:
            out = subprocess.check_output(["rsync", "--version"])  # nosec
            log(out.decode().splitlines()[0])
        except Exception:
            pass


def main() -> int:
    """Parse args and run."""
    args = parse_args()
    # Default: install both if neither flag is set
    do_aws = args.install_aws or not (args.install_aws or args.install_rsync)
    do_rsync = args.install_rsync or not (
        args.install_aws or args.install_rsync
    )

    try:
        do(do_aws=do_aws, do_rsync=do_rsync)
        return 0
    except KeyboardInterrupt:
        log("Interrupted.")
        return 130
    except Exception as e:
        log(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
