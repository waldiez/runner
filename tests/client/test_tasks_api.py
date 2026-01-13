# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.
# flake8: noqa: E501
# pylint: disable=missing-param-doc,missing-return-doc,protected-access
# pyright: reportPrivateUsage=false,reportOptionalMemberAccess=false
"""Test waldiez_runner.client._tasks_api.*."""

import asyncio

import httpx
import pytest
from pytest_httpx import HTTPXMock

# noinspection PyProtectedMember
from waldiez_runner.client._tasks_api import TasksAPIClient
from waldiez_runner.client.auth import Auth


@pytest.fixture(name="client")
def client_fixture(auth: Auth) -> TasksAPIClient:
    """Return a new TasksAPIClient instance."""
    return TasksAPIClient(auth)


def test_configure(client: TasksAPIClient, auth: Auth) -> None:
    """Test client configuration."""
    assert client._auth == auth
    assert client._auth.base_url == "http://localhost:8000"


def test_configure_raises_without_base_url() -> None:
    """Test that configure raises if base_url is not set."""
    auth = Auth()
    auth._base_url = None

    client = TasksAPIClient(auth=None)
    with pytest.raises(ValueError, match="Base URL is required"):
        client.configure(auth)


def test_list_tasks(client: TasksAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test listing tasks."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks",
        json={"items": [{"id": "1"}, {"id": "2"}], "total": 2},
        status_code=200,
    )

    response = client.list_tasks()
    assert response == {"items": [{"id": "1"}, {"id": "2"}], "total": 2}


def test_create_task(client: TasksAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test triggering a task."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks?input_timeout=10",
        json={"task_id": "12345"},
        status_code=200,
    )
    response = client.create_task(b"file_data", "test.txt", input_timeout=10)
    assert response == {"task_id": "12345"}


def test_get_task(client: TasksAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test retrieving task status."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks/12345",
        json={"status": "completed"},
        status_code=200,
    )

    response = client.get_task("12345")
    assert response == {"status": "completed"}


def test_send_user_input(client: TasksAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test sending user input to a task."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks/12345/input",
        status_code=204,
    )

    client.send_user_input("12345", "input_data", "request-1")


def test_download_task_results(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test downloading task results."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks/12345/download",
        content=b"task_result_data",
        status_code=200,
    )

    response = client.download_task_results("12345")
    assert response == b"task_result_data"


def test_cancel_task(client: TasksAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test canceling a task."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks/12345/cancel",
        json={"status": "cancelled"},
        status_code=200,
    )

    response = client.cancel_task("12345")
    assert response == {"status": "cancelled"}


def test_delete_task(client: TasksAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test deleting a task."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks/12345",
        status_code=204,
    )

    client.delete_task("12345")


def test_force_delete_task(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test force deleting a task."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks/12345?force=true",
        status_code=204,
    )

    client.delete_task("12345", force=True)


def test_delete_all_tasks(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test deleting all tasks."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks?force=false",
        status_code=204,
    )

    client.delete_tasks()


def test_force_delete_all_tasks(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test force deleting all tasks."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks?force=true",
        status_code=204,
    )

    client.delete_tasks(force=True)


def test_list_tasks_error(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test listing tasks with an error."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks",
        status_code=500,
        text="Server error",
    )
    with pytest.raises(httpx.HTTPError):
        client.list_tasks()


def test_invalid_client_config() -> None:
    """Test initializing the client without auth."""
    client = TasksAPIClient(auth=None)
    with pytest.raises(ValueError, match="Client is not configured"):
        client.create_task(b"file_data", "test.txt")


def test_http_error_handling(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test handling of HTTP errors."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks?input_timeout=180",
        status_code=500,
        text="Internal Server Error",
    )

    with pytest.raises(httpx.HTTPError):
        client.create_task(b"file_data", "test.txt")


def test_handle_error_sync_callback(auth: Auth) -> None:
    """Test _handle_error with sync callback."""
    messages: list[str] = []

    def on_error(msg: str) -> None:
        messages.append(msg)

    client = TasksAPIClient(auth, on_error=on_error)
    client.handle_error("sync error test")
    assert messages == ["sync error test"]


@pytest.mark.anyio
async def test_a_list_tasks(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test listing tasks asynchronously."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks",
        json={"items": [{"id": "1"}, {"id": "2"}], "total": 2},
        status_code=200,
    )

    response = await client.a_list_tasks()
    assert response == {"items": [{"id": "1"}, {"id": "2"}], "total": 2}


@pytest.mark.anyio
async def test_a_create_task(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test triggering a task asynchronously."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks?input_timeout=10",
        json={"task_id": "12345"},
        status_code=200,
    )

    response = await client.a_create_task(
        b"file_data", "test.txt", input_timeout=10
    )
    assert response == {"task_id": "12345"}


@pytest.mark.anyio
async def test_a_get_task(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test retrieving task status asynchronously."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks/12345",
        json={"status": "completed"},
        status_code=200,
    )

    response = await client.a_get_task("12345")
    assert response == {"status": "completed"}


@pytest.mark.anyio
async def test_a_send_user_input(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test sending user input to a task asynchronously."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks/12345/input",
        status_code=204,
    )

    await client.a_send_user_input("12345", "input_data", "request-1")


@pytest.mark.anyio
async def test_a_download_task_results(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test downloading task results asynchronously."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks/12345/download",
        content=b"task_result_data",
        status_code=200,
    )

    response = await client.a_download_task_results("12345")
    assert response == b"task_result_data"


@pytest.mark.anyio
async def test_a_cancel_task(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test canceling a task asynchronously."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks/12345/cancel",
        json={"status": "cancelled"},
        status_code=200,
    )

    response = await client.a_cancel_task("12345")
    assert response == {"status": "cancelled"}


@pytest.mark.anyio
async def test_a_delete_task(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test deleting a task asynchronously."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks/12345",
        status_code=204,
    )

    await client.a_delete_task("12345")


@pytest.mark.anyio
async def test_a_force_delete_task(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test force deleting a task asynchronously."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks/12345?force=true",
        status_code=204,
    )

    await client.a_delete_task("12345", force=True)


@pytest.mark.anyio
async def test_a_delete_all_tasks(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test deleting all tasks asynchronously."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks?force=false",
        status_code=204,
    )

    await client.a_delete_tasks()


@pytest.mark.anyio
async def test_a_force_delete_all_tasks(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test force deleting all tasks asynchronously."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks?force=true",
        status_code=204,
    )

    await client.a_delete_tasks(force=True)


@pytest.mark.anyio
async def test_a_list_tasks_error(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test listing tasks with an error asynchronously."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks",
        status_code=500,
        text="Server error",
    )
    with pytest.raises(httpx.HTTPError):
        await client.a_list_tasks()


@pytest.mark.anyio
async def test_async_http_error_handling(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test handling of HTTP errors in async methods."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks?input_timeout=180",
        status_code=500,
        text="Internal Server Error",
    )

    with pytest.raises(httpx.HTTPError):
        await client.a_create_task(b"file_data", "test.txt")


@pytest.mark.anyio
async def test_handle_error_async_callback(auth: Auth) -> None:
    """Test _handle_error with async callback."""
    messages: list[str] = []

    async def on_error(msg: str) -> None:
        messages.append(msg)

    client = TasksAPIClient(auth, on_error=on_error)
    client.handle_error("async error test")
    # Let the task complete
    await asyncio.sleep(0)
    assert messages == ["async error test"]
