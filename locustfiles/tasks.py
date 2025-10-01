# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Locust load testing for Waldiez Runner API."""

# pyright: reportUnknownVariableType=false,reportUnknownMemberType=false
import json
import os
import random
import tempfile
from pathlib import Path
from typing import Any

from locust import HttpUser, between, task
from locust.env import Environment

ROOT_DIR = Path(__file__).parent.parent

LOCUST_ENV = ROOT_DIR / ".env.locust"

if LOCUST_ENV.is_file():
    try:
        from dotenv import load_dotenv

        load_dotenv(str(LOCUST_ENV))
    except ImportError:
        pass  # dotenv not installed, will use os.getenv defaults


def get_client_pair(audience: str) -> tuple[str, str]:
    """Get the client_id/client_secret pair from clients.json.

    Parameters
    ----------
    audience : str
        The expected audience: clients, tasks, admin

    Returns
    -------
    tuple[str, str]
        The client_id and client_secret for the pair.
    """
    audience_key = audience.split("-")[0]
    env_key = f"WALDIEZ_RUNNER_{audience_key.upper()}"
    client_id = os.getenv(f"{env_key}_CLIENT_ID", "")
    client_secret = os.getenv(f"{env_key}_CLIENT_SECRET", "")
    if os.path.exists("clients.json"):
        with open("clients.json", "r", encoding="utf-8") as f:
            entries = json.load(f)
        if isinstance(entries, list):
            for entry in entries:
                if (
                    isinstance(entry, dict)
                    and entry.get("audience", "") == f"{audience_key}-api"
                ):
                    client_id = entry.get("client_id", client_id)
                    client_secret = entry.get("client_secret", client_secret)
    return client_id, client_secret


class TasksAPIUser(HttpUser):
    """User focused on task operations with tasks-api audience."""

    wait_time = between(2, 5)  # type: ignore
    host = os.getenv("WALDIEZ_RUNNER_API_HOST", "http://localhost:8000")
    environment: Environment
    access_token: str
    refresh_token: str
    audience: str
    headers: dict[str, str]
    waldiez_file: str | None  # file to upload and trigger task
    flow_env: dict[str, str]

    def on_start(self) -> None:
        """Authenticate with tasks-api audience."""
        tasks_id, tasks_secret = get_client_pair("tasks")
        self._init_waldiez_flow()

        response = self.client.post(
            "/auth/token",
            data={
                "client_id": tasks_id,
                "client_secret": tasks_secret,
            },
            name="/auth/token (Tasks API Login)",
        )

        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self.audience = data["audience"]
            self.headers = {"Authorization": f"Bearer {self.access_token}"}
        else:
            print(f"Tasks API authentication failed: {response.status_code}")
            if self.environment.runner:
                self.environment.runner.quit()

    def _init_waldiez_flow(self) -> None:
        """Check if we have a waldiez flow to upload and run."""
        waldiez_flow = os.getenv("WALDIEZ_RUNNER_WALDIEZ_FLOW", "")
        if waldiez_flow and os.path.exists(waldiez_flow):
            self.waldiez_file = waldiez_flow
        flow_env_keys = os.getenv("WALDIEZ_RUNNER_ENV_KEYS", "")
        self.flow_env = {}
        if flow_env_keys:
            env_keys = filter(
                lambda entry: entry.strip() != "", flow_env_keys.split(",")
            )
            for env_key in env_keys:
                env_val = os.getenv(env_key, "")
                if env_val:
                    self.flow_env[env_key] = env_val

    @task(1)
    def refresh_token_flow(self) -> None:
        """Test token refresh."""
        response = self.client.post(
            "/auth/token/refresh",
            json={
                "refresh_token": self.refresh_token,
                "audience": self.audience,
            },
            name="/auth/token/refresh (Refresh)",
        )

        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self.headers = {"Authorization": f"Bearer {self.access_token}"}

    @task(10)
    def list_my_tasks(self) -> None:
        """List tasks with pagination."""
        params = {
            "page": random.randint(1, 3),  # nosemgrep # nosec
            "size": 10,
        }
        self.client.get(
            "/api/v1/tasks",
            headers=self.headers,
            params=params,
            name="/api/v1/tasks (Paginated)",
        )

    @task(3)
    def search_tasks(self) -> None:
        """Search tasks by term."""
        search_terms = ["test", "workflow", "demo", ""]
        params = {"search": random.choice(search_terms)}  # nosemgrep # nosec

        self.client.get(
            "/api/v1/tasks",
            headers=self.headers,
            params=params,
            name="/api/v1/tasks (Search)",
            catch_response=True,
        )

    @task(2)
    def get_task_details(self) -> None:
        """Get task details."""
        response = self.client.get("/api/v1/tasks", headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])

            if items:
                task_id = random.choice(items)["id"]  # nosemgrep # nosec
                self.client.get(
                    f"/api/v1/tasks/{task_id}",
                    headers=self.headers,
                    name="/api/v1/tasks/{task_id} (Details)",
                    catch_response=True,
                )

    @task(1)
    def update_task(self) -> None:
        """Update a task."""
        response = self.client.get("/api/v1/tasks", headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])

            if items:
                task_id = random.choice(items)["id"]  # nosemgrep # nosec
                timeout = random.choice(  # nosemgrep # nosec
                    [120, 180, 240, 300],
                )
                update_data = {
                    "input_timeout": timeout,
                }

                self.client.patch(
                    f"/api/v1/tasks/{task_id}",
                    json=update_data,
                    headers=self.headers,
                    name="/api/v1/tasks/{task_id} (Update)",
                    catch_response=True,
                )

    @task(5)
    def trigger_task(self) -> None:
        """Trigger a task."""
        if not self.waldiez_file:
            return

        # Create a temporary copy with a unique name to avoid duplicate task_ids
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".waldiez", delete=False
        ) as tmp_file:
            tmp_path = tmp_file.name
            # Copy the original file content to the temp file
            with open(self.waldiez_file, "rb") as src:
                tmp_file.write(src.read())
        # pylint: disable=too-many-try-statements
        try:
            # Upload the file
            with open(tmp_path, "rb") as f:
                files = {
                    "file": (os.path.basename(tmp_path), f, "application/json")
                }
                data: dict[str, Any] = {}
                # Add environment variables if any
                if self.flow_env:
                    data["env_vars"] = json.dumps(self.flow_env)

                with self.client.post(
                    "/api/v1/tasks",
                    files=files,
                    data=data,
                    headers=self.headers,
                    name="/api/v1/tasks (Upload & Trigger)",
                    catch_response=True,
                ) as response:
                    if response.status_code < 400:
                        response.success()
                    else:
                        response.failure(
                            "Task upload failed with status "
                            f"{response.status_code}"
                        )
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @task(2)
    def cancel_task(self) -> None:
        """Cancel a running task."""
        response = self.client.get("/api/v1/tasks", headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])

            # Filter for active tasks
            active_items = [
                item
                for item in items
                if item.get("status")
                in ["pending", "running", "waiting_for_input"]
            ]

            if active_items:
                task_id = random.choice(active_items)["id"]  # nosemgrep # nosec
                self.client.post(
                    f"/api/v1/tasks/{task_id}/cancel",
                    headers=self.headers,
                    name="/api/v1/tasks/{task_id}/cancel",
                    catch_response=True,
                )
