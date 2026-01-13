# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

"""Load testing script for Waldiez Runner using Locust."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent

ENV_LOCUST = ROOT_DIR / ".env.locust"

if ENV_LOCUST.exists():
    # Load environment variables
    try:
        from dotenv import load_dotenv

        load_dotenv(str(ENV_LOCUST))
    except ImportError:
        print("Warning: python-dotenv not installed, using os.environ")


def check_locust_installed() -> bool:
    """Check if locust is installed.

    Returns
    -------
    bool
        True if locust is installed, False otherwise.
    """
    return shutil.which("locust") is not None


def install_locust() -> bool:
    """Install locust using pip.

    Returns
    -------
    bool
        True if installation succeeded, False otherwise.
    """
    print("Installing locust...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "locust"],
            check=True,
            cwd=ROOT_DIR,
        )
        print("✓ Locust installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install locust: {e}")
        return False


def _save_config(config: dict[str, str]) -> None:
    """Save the config to .env.locust."""
    # Write to .env.locust file
    dot_env = ROOT_DIR / ".env.locust"

    # Read existing file to preserve structure
    existing_lines = []
    if dot_env.exists():
        with open(dot_env, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()

    # Update or append configuration
    with open(dot_env, "w", encoding="utf-8") as f:
        if not existing_lines:
            # Write header if new file
            f.write("# Waldiez Runner Load Testing Configuration\n\n")

        # Track which keys we've written
        written_keys: set[str] = set()

        # Update existing lines or keep them as-is
        for line in existing_lines:
            line_stripped = line.strip()
            # Keep comments and empty lines
            if not line_stripped or line_stripped.startswith("#"):
                f.write(line)
            else:
                # Parse key=value
                if "=" in line_stripped:
                    key = line_stripped.split("=")[0].strip()
                    if key in config:
                        # Update with new value
                        f.write(f"{key}={config[key]}\n")
                        written_keys.add(key)
                    else:
                        # Keep existing line
                        f.write(line)

        # Add new keys not in existing file
        if written_keys != set(config.keys()):
            f.write("\n# New configuration values\n")
            for key, value in config.items():
                if key not in written_keys:
                    f.write(f"{key}={value}\n")

    print(f"\n✓ Configuration saved to {dot_env.relative_to(Path.cwd())}")


def setup_environment() -> None:
    """Interactive setup for environment variables."""
    print("\n=== Locust Configuration Setup ===\n")

    config: dict[str, str] = {}

    # API Configuration
    print("API Configuration:")
    api_host = input("  API Host [http://localhost:8000]: ").strip()
    config["WALDIEZ_RUNNER_API_HOST"] = api_host or "http://localhost:8000"

    # Load Test Configuration
    print("\nLoad Test Configuration:")
    users = input("  Number of users [50]: ").strip()
    config["LOCUST_USERS"] = users or "50"

    spawn_rate = input("  Spawn rate (users/sec) [5]: ").strip()
    config["LOCUST_SPAWN_RATE"] = spawn_rate or "5"

    run_time = input("  Run time in seconds [120]: ").strip()
    config["LOCUST_RUN_TIME"] = run_time or "120"

    # Client Credentials
    print("\n--- Client Credentials (optional, press Enter to skip) ---")
    print("Note: Leave empty if using clients.json file\n")

    print("Tasks API Credentials:")
    tasks_id = input("  Tasks Client ID: ").strip()
    if tasks_id:
        config["WALDIEZ_RUNNER_TASKS_CLIENT_ID"] = tasks_id
        config["WALDIEZ_RUNNER_TASKS_CLIENT_SECRET"] = input(
            "  Tasks Client Secret: "
        ).strip()

    print("\nClients API Credentials:")
    clients_id = input("  Clients Client ID: ").strip()
    if clients_id:
        config["WALDIEZ_RUNNER_CLIENTS_CLIENT_ID"] = clients_id
        config["WALDIEZ_RUNNER_CLIENTS_CLIENT_SECRET"] = input(
            "  Clients Client Secret: "
        ).strip()

    print("\nAdmin User Credentials:")
    admin_id = input("  Admin Client ID: ").strip()
    if admin_id:
        config["WALDIEZ_RUNNER_ADMIN_CLIENT_ID"] = admin_id
        config["WALDIEZ_RUNNER_ADMIN_CLIENT_SECRET"] = input(
            "  Admin Client Secret: "
        ).strip()

    # Waldiez Flow Configuration
    print("\n--- Waldiez Flow Configuration (optional) ---")
    flow_path = input("  Path to .waldiez flow file: ").strip()
    if flow_path:
        config["WALDIEZ_RUNNER_WALDIEZ_FLOW"] = flow_path
        prompt = (
            "  Environment variable keys "
            "(comma-separated, e.g., OPENAI_API_KEY,ANTHROPIC_API_KEY): "
        )
        env_keys = input(prompt).strip()
        if env_keys:
            config["WALDIEZ_RUNNER_ENV_KEYS"] = env_keys
            print("\n  Enter values for the environment variables:")
            for key in env_keys.split(","):
                key = key.strip()
                if key:
                    value = input(f"    {key}: ").strip()
                    if value:
                        config[key] = value

    _save_config(config)


def run_locust_web(
    host: str | None = None,
    users: int | None = None,
    spawn_rate: int | None = None,
    debug: bool = False,
) -> None:
    """Start locust in web UI mode.

    Parameters
    ----------
    host : str | None
        Override the API host
    users : int | None
        Override the number of users
    spawn_rate : int | None
        Override the spawn rate
    debug : bool
        Enable debug logging
    """
    if not check_locust_installed():
        msg = (
            "✗ Locust is not installed. "
            "Run 'python scripts/load.py install' first."
        )
        print(msg)
        sys.exit(1)

    dot_env = ROOT_DIR / ".env.locust"
    if not dot_env.exists():
        print(
            "✗ .env.locust not found. Run 'python scripts/load.py setup' first."
        )
        sys.exit(1)

    print("\n=== Starting Locust Web UI ===\n")
    print("Access the web interface at: http://localhost:8089\n")

    locustfile = ROOT_DIR / "locustfiles" / "tasks.py"

    cmd = ["locust", "-f", str(locustfile)]

    # Add optional parameters
    if host:
        cmd.extend(["--host", host])
    if users:
        cmd.extend(["--users", str(users)])
    if spawn_rate:
        cmd.extend(["--spawn-rate", str(spawn_rate)])
    if debug:
        cmd.extend(["--loglevel", "DEBUG"])

    try:
        subprocess.run(cmd, cwd=ROOT_DIR, check=True)
    except KeyboardInterrupt:
        print("\n✓ Locust stopped")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to run locust: {e}")
        sys.exit(1)


def run_locust_headless(
    host: str | None = None,
    users: int | None = None,
    spawn_rate: int | None = None,
    run_time: int | None = None,
    debug: bool = False,
) -> None:
    """Run locust in headless mode.

    Parameters
    ----------
    host : str | None
        Override the API host
    users : int | None
        Override the number of users
    spawn_rate : int | None
        Override the spawn rate
    run_time : int | None
        Override the run time in seconds
    debug : bool
        Enable debug logging
    """
    if not check_locust_installed():
        msg = (
            "✗ Locust is not installed. Run "
            "'python scripts/load.py install' "
            "or 'pip install locust' first."
        )
        print(msg)
        sys.exit(1)

    # Get configuration from environment or arguments
    final_host: str = (
        host
        if host
        else os.getenv("WALDIEZ_RUNNER_API_HOST", "http://localhost:8000")
    )
    final_users = users or int(os.getenv("LOCUST_USERS", "50"))
    final_spawn_rate = spawn_rate or int(os.getenv("LOCUST_SPAWN_RATE", "5"))
    final_run_time = run_time or int(os.getenv("LOCUST_RUN_TIME", "120"))

    print("\n=== Running Locust in Headless Mode ===\n")
    print(f"Host: {final_host}")
    print(f"Users: {final_users}")
    print(f"Spawn rate: {final_spawn_rate}/sec")
    print(f"Run time: {final_run_time}s")
    if debug:
        print("Log level: DEBUG")
    print()

    locustfiles = ROOT_DIR / "locustfiles"

    cmd: list[str] = [
        "locust",
        "-f",
        f"{locustfiles}",
        "--headless",
        "--users",
        f"{final_users}",
        "--spawn-rate",
        f"{final_spawn_rate}",
        "--run-time",
        f"{final_run_time}s",
        "--host",
        final_host,
        # cspell: disable-next-line
        "--autostart",
        # cspell: disable-next-line
        "--autoquit",
        "10",
    ]

    if debug:
        cmd.extend(["--loglevel", "DEBUG"])

    try:
        subprocess.run(cmd, cwd=ROOT_DIR, check=True)
        print("\n✓ Load test completed")
    except KeyboardInterrupt:
        print("\n✓ Locust stopped")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to run locust: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the load testing script."""
    parser = argparse.ArgumentParser(
        description="Waldiez Runner Load Testing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands"
    )

    # Install command
    subparsers.add_parser(
        "install", help="Install locust if not already installed"
    )

    # Setup command
    subparsers.add_parser(
        "setup", help="Setup environment variables in .env.locust"
    )

    # Web command
    web_parser = subparsers.add_parser(
        "web", help="Start locust in web UI mode (interactive)"
    )
    web_parser.add_argument("--host", help="API host URL")
    web_parser.add_argument(
        "--users", type=int, help="Number of users to simulate"
    )
    web_parser.add_argument(
        "--spawn-rate", type=int, help="Rate to spawn users at (users/sec)"
    )
    web_parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging"
    )

    # Run command
    run_parser = subparsers.add_parser(
        "run", help="Run locust in headless mode (automated)"
    )
    run_parser.add_argument("--host", help="API host URL")
    run_parser.add_argument(
        "--users", type=int, help="Number of users to simulate"
    )
    run_parser.add_argument(
        "--spawn-rate", type=int, help="Rate to spawn users at (users/sec)"
    )
    run_parser.add_argument(
        "--run-time",
        type=int,
        help="Stop after the specified amount of seconds",
    )
    run_parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "install":
        if check_locust_installed():
            print("✓ Locust is already installed")
        else:
            if not install_locust():
                sys.exit(1)

    elif args.command == "setup":
        setup_environment()

    elif args.command == "web":
        run_locust_web(
            host=args.host,
            users=args.users,
            spawn_rate=args.spawn_rate,
            debug=args.debug,
        )

    elif args.command == "run":
        run_locust_headless(
            host=args.host,
            users=args.users,
            spawn_rate=args.spawn_rate,
            run_time=args.run_time,
            debug=args.debug,
        )


if __name__ == "__main__":
    main()
