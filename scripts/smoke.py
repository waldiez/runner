# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Simple checks after startup with no extra data.

This script is a simple smoke test to ensure the API is working as expected.

- Use the initial client_id/client_secret pair to get an access token.
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
- Send Task input via HTTP.
- Run two parallel tasks (with input).

Not covered (yet?) in this script:

- Use the client in the package for the requests
- WebSocket connection for task input/output.
"""

import asyncio
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any

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
EXAMPLE_2_FLOW_PATH = ROOT_DIR / "examples" / "dummy_with_input2.waldiez"

HTTPX_CLIENT = httpx.AsyncClient(timeout=30)

os.environ["PYTHONUNBUFFERED"] = "1"  # Force stdout to be unbuffered.


def in_container() -> bool:
    """ "Check if we are running in a container.

    Returns
    -------
    bool
        Whether we are running in a container.
    """
    in_docker = os.path.isfile("/.dockerenv")
    in_container_env = os.path.isfile("/run/.containerenv")
    return in_docker or in_container_env


async def random_sleep(smaller_than: int) -> None:
    """Sleep for a random time.

    Parameters
    ----------
    smaller_than : int
        The maximum time to sleep.
    """
    sleep_duration = secrets.randbelow(smaller_than)
    sleep_duration = max(sleep_duration, 2)
    print(f"Sleeping for {sleep_duration} seconds.")
    await asyncio.sleep(sleep_duration)


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


async def list_clients(access_token: str) -> dict[str, Any]:
    """List clients.

    Parameters
    ----------
    access_token : str
        The access token.

    Returns
    -------
    dict[str, Any]
        The response.
    """
    response = await HTTPX_CLIENT.get(
        CLIENTS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json()


async def create_client(access_token: str, audience: str) -> dict[str, Any]:
    """Create a client.

    Parameters
    ----------
    access_token : str
        The access token.
    audience : str
        The audience.
    Returns
    -------
    dict[str, Any]
        The response.
    """
    api_type = audience.split("-")[0].capitalize()
    response = await HTTPX_CLIENT.post(
        CLIENTS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "audience": audience,
            "name": "smoke-client",
            "description": f"A client for the {api_type} API.",
        },
    )
    response.raise_for_status()
    return response.json()


async def list_tasks(access_token: str) -> dict[str, Any]:
    """List tasks.

    Parameters
    ----------
    access_token : str
        The access token.

    Returns
    -------
    dict[str, Any]
        The response.
    """
    response = await HTTPX_CLIENT.get(
        TASKS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json()


async def create_task(
    access_token: str,
    example_flow_path: Path,
    input_timeout: int,
) -> dict[str, Any]:
    """Create a task.

    Parameters
    ----------
    access_token : str
        The access token.
    example_flow_path : Path
        The example flow path.
    input_timeout : int
        The input timeout.

    Returns
    -------
    dict[str, Any]
        The response.
    """
    response = await HTTPX_CLIENT.post(
        TASKS_URL + f"?input_timeout={input_timeout}",
        headers={"Authorization": f"Bearer {access_token}"},
        files={
            "file": (
                example_flow_path.name,
                example_flow_path.open("rb"),
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
        f"{TASKS_URL}/{task_id}?force=true",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    if response.status_code != 204:
        raise AssertionError("The task should be deleted.")
    return


async def clients_check() -> tuple[dict[str, Any], str]:
    """Check the clients API.

    Returns
    -------
    tuple[dict[str, Any], str]
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


async def cancel_task(
    task_id: str,
    tasks_access_token: str,
    might_not_be_active: bool = False,
) -> None:
    """Cancel a task.

    Parameters
    ----------
    task_id : str
        The task ID.
    tasks_access_token : str
        The tasks access token.
    might_not_be_active: bool
        If true, we do not raise if the request fails

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
        print(response.json())
        if not might_not_be_active:
            raise AssertionError("The task should be cancelled.")
        print("It's probably ok, using fake redis")
    return


async def tasks_check(client: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Check the tasks API.

    Parameters
    ----------
    client : dict[str, Any]
        The client.

    Returns
    -------
    tuple[dict[str, Any], str]
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
        task = await create_task(
            tasks_access_token,
            EXAMPLE_FLOW_PATH,
            input_timeout=5,
        )
    except httpx.HTTPStatusError as e:
        print(e.response.json())
        raise AssertionError("The task client should create tasks.") from e
    print("New task:")
    print(json.dumps(task, indent=2))
    return task, tasks_access_token


async def send_user_input(
    task_id: str,
    input_request_id: str,
    tasks_access_token: str,
    user_input: str,
) -> None:
    """Send user input.

    Parameters
    ----------
    task_id : str
        The task ID.
    input_request_id : str
        The input request ID.
    tasks_access_token : str
        The tasks access token.
    user_input : str
        The user input.

    Raises
    ------
    AssertionError
        If the task is not deleted.
    """
    response = await HTTPX_CLIENT.post(
        f"{TASKS_URL}/{task_id}/input",
        headers={"Authorization": f"Bearer {tasks_access_token}"},
        json={"request_id": input_request_id, "data": user_input},
    )
    response.raise_for_status()
    if response.status_code != 204:
        raise AssertionError("The input should be accepted.")
    return


# pylint: disable=too-complex
async def task_status_check(  # noqa
    task: dict[str, Any], tasks_access_token: str
) -> None:
    """Check the task status.

    Parameters
    ----------
    task : dict[str, Any]
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
    user_inputs = 0
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
        if reties > 10 and not in_container():
            # not using real redis, status not changing
            await cancel_task(
                task_id=task_id,
                tasks_access_token=tasks_access_token,
                might_not_be_active=True,
            )
            await delete_task(task_id, tasks_access_token)
            return
        await asyncio.sleep(2)
    if task["status"] == "PENDING":
        raise AssertionError("The task should change status.")
    if task["status"] in ("RUNNING", "WAITING_FOR_INPUT"):
        print("The task is running.")
        for index in range(30):
            response = await HTTPX_CLIENT.get(
                task_url,
                headers={"Authorization": f"Bearer {tasks_access_token}"},
            )
            response.raise_for_status()
            task = response.json()
            print("Task by id:")
            print(json.dumps(task, indent=2))
            sleep_duration = (
                2 * (index + 1) if task["status"] == "RUNNING" else 2
            )
            if task["status"] == "COMPLETED":
                break
            if task["status"] == "FAILED":
                raise AssertionError("The task should not fail.")
            if task["status"] == "CANCELLED":
                raise AssertionError("The task should not be cancelled.")
            if task["status"] == "WAITING_FOR_INPUT":
                await send_user_input(
                    task["id"],
                    task["input_request_id"],
                    tasks_access_token,
                    f"This is a test input #{user_inputs + 1}",
                )
                user_inputs += 1
            await asyncio.sleep(sleep_duration)
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


async def handle_one_task(
    tasks_access_token: str,
    example_flow_path: Path,
    input_timeout: int,
) -> dict[str, Any]:
    """Handle one task.
    Parameters
    ----------
    tasks_access_token : str
        The tasks access token.
    example_flow_path : Path
        The example flow path.
    input_timeout : int
        The input timeout.

    Returns
    -------
    dict[str, Any]
        The task.

    Raises
    ------
    AssertionError
        If a check fails
    """
    # create a task
    task = await create_task(
        access_token=tasks_access_token,
        example_flow_path=example_flow_path,
        input_timeout=input_timeout,
    )
    print("New task:")
    print(json.dumps(task, indent=2))
    # get the task id
    task_id = task["id"]
    # get the task url
    task_url = f"{TASKS_URL}/{task_id}"
    # get the task by id
    response = await HTTPX_CLIENT.get(
        task_url,
        headers={"Authorization": f"Bearer {tasks_access_token}"},
    )
    response.raise_for_status()
    task = response.json()
    print("Task by id:")
    print(json.dumps(task, indent=2))
    # check the task status (in a loop)
    # it should change from pending to running to completed

    max_retries = 100
    retries = 0
    user_inputs = 0

    while retries < max_retries:
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
        if task["status"] == "CANCELLED":
            raise AssertionError("The task should not be cancelled.")
        retries += 1
        time_to_sleep = (
            2 * (retries + 1) if task["status"] != "WAITING_FOR_INPUT" else 5
        )
        if task["status"] == "WAITING_FOR_INPUT":
            # random small delay
            await random_sleep(input_timeout // 2)
            await send_user_input(
                task["id"],
                task["input_request_id"],
                tasks_access_token,
                f"Input for {example_flow_path.name} #{user_inputs + 1}",
            )
            user_inputs += 1
            print(f"Sent user input #{user_inputs}")
        await asyncio.sleep(time_to_sleep)
    if task["status"] == "COMPLETED":
        print("The task is completed.")
        archive = await download_task_archive(task_id, tasks_access_token)
        print("Task archive downloaded.")
        print(f"Task archive size: {len(archive)}")
    # delete the task
    await delete_task(task_id, tasks_access_token)
    print("Task deleted.")
    return task


async def test_running_two_parallel_tasks(tasks_access_token: str) -> None:
    """Test running two parallel tasks that both require user input.

    Parameters
    ----------
    tasks_access_token : str
        The tasks access token.

    Raises
    ------
    AssertionError
        If a check fails
    """
    timeout1 = 10
    timeout2 = 20

    # Run both tasks in parallel
    result1_task = handle_one_task(
        tasks_access_token=tasks_access_token,
        example_flow_path=EXAMPLE_FLOW_PATH,
        input_timeout=timeout1,
    )

    result2_task = handle_one_task(
        tasks_access_token=tasks_access_token,
        example_flow_path=EXAMPLE_2_FLOW_PATH,
        input_timeout=timeout2,
    )

    results = await asyncio.gather(result1_task, result2_task)

    result1, result2 = results
    print("First task result:")
    print(json.dumps(result1, indent=2))
    print("Second task result:")
    print(json.dumps(result2, indent=2))
    # Check if both tasks completed successfully
    if result1["status"] != "COMPLETED":
        raise AssertionError("The first task should be completed.")
    if result2["status"] != "COMPLETED":
        raise AssertionError("The second task should be completed.")

    print("Both parallel tasks completed successfully.")


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
    if in_container() or "--force" in sys.argv:
        await test_running_two_parallel_tasks(tasks_access_token)
    await delete_client(
        client["client_id"], tasks_access_token, clients_access_token
    )
    print("All checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
