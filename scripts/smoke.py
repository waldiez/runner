# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Simple checks after startup with no extra data.

- Use the client_id/client_secret to get an access token.
- Ensure it cannot be used to list tasks (it is for clients only).
- Ensure it can be used to list and create clients.
- Generate one client and ensure it can be used to list tasks.
- Ensure the client cannot be used to list clients.
- Ensure the client can be used to list and create tasks.
- Generate one task and ensure it can be retrieved by id.
- Ensure the task status changes from pending to running.
- If the task is running, wait for it to complete.
- If the task is completed, download the archive.
- Ensure we cannot delete the client with the tasks access token.
- Ensure we can delete the client with the clients access token.

This script is a simple smoke test to ensure the API is working as expected.

Not covered (yet?):
- Send user's input using websockets or HTTP.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple

import httpx
from dotenv import load_dotenv

HERE = Path(__file__).parent
ROOT_DIR = HERE.parent
load_dotenv(ROOT_DIR / ".env")

ENV_PREFIX = "WALDIEZ_RUNNER_"
PORT = int(os.getenv(f"{ENV_PREFIX}PORT", "8000"))
DOMAIN_NAME = os.getenv(f"{ENV_PREFIX}DOMAIN_NAME", "localhost")
LOCAL_CLIENT_ID = os.getenv(f"{ENV_PREFIX}LOCAL_CLIENT_ID", "local-client")
LOCAL_CLIENT_SECRET = os.getenv(
    f"{ENV_PREFIX}LOCAL_CLIENT_SECRET", "local-secret"
)

TOKEN_URL = f"http://localhost:{PORT}/auth/token"
CLIENTS_URL = f"http://localhost:{PORT}/api/v1/clients"
TASKS_URL = f"http://localhost:{PORT}/api/v1/tasks"
EXAMPLE_FLOW_PATH = ROOT_DIR / "examples" / "dummy_with_input.waldiez"
# EXAMPLE_FLOW_PATH = ROOT_DIR / "examples" / "dummy.waldiez"

HTTPX_CLIENT = httpx.AsyncClient(timeout=30)


async def get_access_token(client_id: str, client_secret: str) -> str:
    """Get an access token.

    Parameters
    ----------
    client_id : str
        The client ID.
    client_secret : str
        The client secret.

    Returns
    -------
    str
        The access token.
    """
    response = await HTTPX_CLIENT.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def list_clients(access_token: str) -> Dict[str, Any]:
    """List clients.

    Parameters
    ----------
    access_token : str
        The access token.

    Returns
    -------
    Dict[str, Any]
        The response.
    """
    response = await HTTPX_CLIENT.get(
        CLIENTS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json()


async def create_client(access_token: str, audience: str) -> Dict[str, Any]:
    """Create a client.

    Parameters
    ----------
    access_token : str
        The access token.
    audience : str
        The audience.
    Returns
    -------
    Dict[str, Any]
        The response.
    """
    api_type = audience.split("-")[0].capitalize()
    response = await HTTPX_CLIENT.post(
        CLIENTS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "audience": audience,
            "description": f"A client for the {api_type} API.",
        },
    )
    response.raise_for_status()
    return response.json()


async def list_tasks(access_token: str) -> Dict[str, Any]:
    """List tasks.

    Parameters
    ----------
    access_token : str
        The access token.

    Returns
    -------
    Dict[str, Any]
        The response.
    """
    response = await HTTPX_CLIENT.get(
        TASKS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json()


async def create_task(access_token: str) -> Dict[str, Any]:
    """Create a task.

    Parameters
    ----------
    access_token : str
        The access token.
    Returns
    -------
    Dict[str, Any]
        The response.
    """
    response = await HTTPX_CLIENT.post(
        TASKS_URL + "?input_timeout=5",
        headers={"Authorization": f"Bearer {access_token}"},
        files={
            "file": (
                EXAMPLE_FLOW_PATH.name,
                EXAMPLE_FLOW_PATH.open("rb"),
                "application/json",
            )
        },
    )
    response.raise_for_status()
    return response.json()


async def download_task_archive(task_id: str, access_token: str) -> bytes:
    """Download the task archive.

    Parameters
    ----------
    task_id : str
        The task ID.
    access_token : str
        The access token.

    Returns
    -------
    bytes
        The archive.
    """
    response = await HTTPX_CLIENT.get(
        f"{TASKS_URL}/{task_id}/download",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    # a zip/FileResponse is returned
    return response.content


async def delete_task(task_id: str, access_token: str) -> None:
    """Delete a task.

    Parameters
    ----------
    task_id : str
        The task ID.
    access_token : str
        The access token.

    Raises
    ------
    AssertionError
        If the task is not deleted.
    """
    response = await HTTPX_CLIENT.delete(
        f"{TASKS_URL}/{task_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    if response.status_code != 204:
        raise AssertionError("The task should be deleted.")
    return


async def clients_check() -> Tuple[Dict[str, Any], str]:
    """Check the clients API.

    Returns
    -------
    Tuple[Dict[str, Any], str]
        The new client and the first client's access token.

    Raises
    ------
    AssertionError
        If a check fails
    """
    clients_access_token = await get_access_token(
        LOCAL_CLIENT_ID, LOCAL_CLIENT_SECRET
    )
    if not clients_access_token:
        raise AssertionError("No access token returned.")

    print("Clients-api access token:\n", clients_access_token)

    # Ensure it cannot be used to list tasks (it is for clients only).
    try:
        await list_tasks(clients_access_token)
    except httpx.HTTPStatusError:
        print("Good, the local access token cannot be used to list tasks.")
    else:
        raise AssertionError("The local access token should not list tasks.")

    # Ensure it can be used to list and create clients.
    clients = await list_clients(clients_access_token)
    print("Clients:")
    print(json.dumps(clients, indent=2))

    client_audience = "tasks-api"
    client = await create_client(clients_access_token, client_audience)
    print("New task client:")
    print(json.dumps(client, indent=2))
    return client, clients_access_token


async def cancel_task(task_id: str, tasks_access_token: str) -> None:
    """Cancel a task.

    Parameters
    ----------
    task_id : str
        The task ID.
    tasks_access_token : str
        The tasks access token.

    Raises
    ------
    AssertionError
        If the task is not deleted.
    """
    response = await HTTPX_CLIENT.post(
        f"{TASKS_URL}/{task_id}/cancel",
        headers={"Authorization": f"Bearer {tasks_access_token}"},
    )
    response.raise_for_status()
    if response.status_code != 204:
        raise AssertionError("The task should be cancelled.")
    return


async def tasks_check(client: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """Check the tasks API.

    Parameters
    ----------
    client : Dict[str, Any]
        The client.

    Returns
    -------
    Tuple[Dict[str, Any], str]
        The task and the tasks access token.

    Raises
    ------
    AssertionError
        If a check fails
    """
    # Generate one client and ensure it can be used to list tasks.
    tasks_access_token = await get_access_token(
        client["client_id"], client["client_secret"]
    )
    if not tasks_access_token:
        raise AssertionError("No access token returned.")
    print("Tasks-api access token:\n", tasks_access_token)
    tasks = await list_tasks(tasks_access_token)
    print("Tasks:")
    print(json.dumps(tasks, indent=2))

    # Ensure the client cannot be used to list clients.
    try:
        await list_clients(tasks_access_token)
    except httpx.HTTPStatusError:
        print("Good, the task client cannot be used to list clients.")
    else:
        raise AssertionError(
            "The task client should not be able to list clients."
        )

    # Ensure the client can be used to list and create tasks.
    try:
        tasks = await list_tasks(tasks_access_token)
        print("Tasks:")
        print(json.dumps(tasks, indent=2))
    except httpx.HTTPStatusError as e:
        raise AssertionError("The task client should list tasks.") from e

    try:
        task = await create_task(tasks_access_token)
    except httpx.HTTPStatusError as e:
        print(e.response.json())
        raise AssertionError("The task client should create tasks.") from e
    print("New task:")
    print(json.dumps(task, indent=2))
    return task, tasks_access_token


async def task_status_check(
    task: Dict[str, Any], tasks_access_token: str
) -> None:
    """Check the task status.

    Parameters
    ----------
    task : Dict[str, Any]
        The task (initially pending).
    tasks_access_token : str
        The tasks access token.

    Raises
    ------
    AssertionError
        If a check fails
    """
    # it should change from pending to running to completed
    reties = 0
    task_id = task["id"]
    task_url = f"{TASKS_URL}/{task_id}"
    # get the task by id
    while task["status"] == "PENDING" and reties < 20:
        response = await HTTPX_CLIENT.get(
            task_url,
            headers={"Authorization": f"Bearer {tasks_access_token}"},
        )
        response.raise_for_status()
        task = response.json()
        print("Task by id:")
        print(json.dumps(task, indent=2))
        if task["status"] == "FAILED":
            raise AssertionError("The task should not fail.")
        reties += 1
        await asyncio.sleep(2)
    if task["status"] == "PENDING":
        raise AssertionError("The task should change status.")
    if task["status"] == "RUNNING":
        print("The task is running.")
        for index in range(20):
            response = await HTTPX_CLIENT.get(
                task_url,
                headers={"Authorization": f"Bearer {tasks_access_token}"},
            )
            response.raise_for_status()
            task = response.json()
            print("Task by id:")
            print(json.dumps(task, indent=2))
            if task["status"] == "COMPLETED":
                break
            if task["status"] == "FAILED":
                raise AssertionError("The task should not fail.")
            await asyncio.sleep(2 * (index + 1))
    if task["status"] == "COMPLETED":
        print("The task is completed.")
        archive = await download_task_archive(task_id, tasks_access_token)
        print("Task archive downloaded.")
        print(f"Task archive size: {len(archive)}")
    else:
        await cancel_task(task_id, tasks_access_token)
        raise AssertionError("The task should be completed by now.")
    await delete_task(task_id, tasks_access_token)
    print("Task deleted.")
    return


async def delete_client(
    client_id: str, tasks_access_token: str, clients_access_token: str
) -> None:
    """Delete a client.

    Parameters
    ----------
    client_id : str
        The client ID.
    tasks_access_token : str
        The tasks access token.
    clients_access_token : str
        The clients access token.

    Raises
    ------
    AssertionError
        If the client is not deleted.
    """
    first_response = await HTTPX_CLIENT.delete(
        f"{CLIENTS_URL}/{client_id}",
        headers={"Authorization": f"Bearer {tasks_access_token}"},
    )
    try:
        first_response.raise_for_status()
    except httpx.HTTPStatusError:
        print("Good, the task client cannot delete clients.")
    else:
        raise AssertionError("The task client should not delete clients.")
    second_response = await HTTPX_CLIENT.delete(
        f"{CLIENTS_URL}/{client_id}",
        headers={"Authorization": f"Bearer {clients_access_token}"},
    )
    second_response.raise_for_status()
    if second_response.status_code != 204:
        raise AssertionError("The client should be deleted.")
    print("Client deleted.")
    return


async def main() -> None:
    """Run the checks.

    Raises
    ------
    AssertionError
        If a check fails
    """
    client, clients_access_token = await clients_check()
    task, tasks_access_token = await tasks_check(client)
    await task_status_check(task, tasks_access_token)
    await delete_client(
        client["client_id"], tasks_access_token, clients_access_token
    )
    print("All checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
