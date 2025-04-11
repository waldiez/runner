# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Setup script for testing Docker Compose with Vagrant."""
import argparse
import platform
import subprocess
import sys
from typing import List

ALL_VM_BOXES = ["ubuntu", "debian", "fedora", "centos", "rocky", "arch"]


def get_vm_boxes() -> List[str]:
    """Get the list of VM boxes to test.

    Returns
    -------
    list
        List of VM box names.
    """
    machine_lower = platform.machine().lower()
    if "x86_64" in machine_lower or "amd64" in machine_lower:
        return ALL_VM_BOXES
    return [box for box in ALL_VM_BOXES if box not in ["debian", "arch"]]


AVAILABLE_VM_BOXES = get_vm_boxes()


def check_vagrant() -> bool:
    """Check if Vagrant is installed and available in PATH.

    Returns
    -------
    bool
        True if Vagrant is installed, False otherwise.
    """
    # pylint: disable=broad-exception-caught, too-many-try-statements
    try:
        result = subprocess.run(  # nosemgrep # nosec
            ["vagrant", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print("Vagrant is not installed or not in PATH.")
            return False
        print(result.stdout.strip())
    except FileNotFoundError:
        print("Vagrant is not installed or not in PATH.")
        return False
    except Exception as e:
        print(f"Error checking Vagrant version: {e}")
        return False
    return True


def run_command(cmd: List[str], cwd: str | None = None) -> bool:
    """Run a command in a subprocess and return True if successful.

    Parameters
    ----------
    cmd : list
        The command to run as a list of strings.
    cwd : str, optional
        The working directory to run the command in.

    Returns
    -------
    bool
        True if the command was successful, False otherwise.
    """
    cmd_str = " ".join(cmd)
    print(f"Running: {cmd_str}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=None,  # Inherit parent
        stderr=None,
        check=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result.returncode == 0


def run_vm(name: str) -> bool:
    """Run a Vagrant VM with the specified name.

    Parameters
    ----------
    name : str
        The name of the VM to run.
    Returns
    -------
    bool
        True if the VM was successfully started, False otherwise.
    """
    print(f"Testing {name}")
    if not run_command(["vagrant", "up", name]):
        return False
    compose_calls = [
        "config",
        "up -d",
        "ps",
        "down",
    ]
    for call in compose_calls:
        if not run_command(
            [
                "vagrant",
                "ssh",
                name,
                "-c",
                f"docker compose -f /home/vagrant/compose.yaml {call}",
            ]
        ):
            return False
    if not run_command(["vagrant", "destroy", "-f", name]):
        return False
    return True


def main() -> None:
    """Main function to run the script."""
    if not check_vagrant():
        print("Vagrant is not installed or not in PATH.")
        sys.exit(1)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--box",
        help="Test only one box (e.g. ubuntu)",
        choices=AVAILABLE_VM_BOXES,
    )
    parser.add_argument("--all", action="store_true", help="Test all boxes")
    args = parser.parse_args()
    try:
        if args.all:
            for box in AVAILABLE_VM_BOXES:
                run_vm(box)
        elif args.box:
            if args.box not in AVAILABLE_VM_BOXES:
                print(f"Unknown box: {args.box}")
                sys.exit(1)
            run_vm(args.box)
        else:
            parser.print_help()
            sys.exit(0)
    finally:
        run_command(["vagrant", "destroy", "-f"])


if __name__ == "__main__":
    main()
