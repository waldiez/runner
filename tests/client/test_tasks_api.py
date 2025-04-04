# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# flake8: noqa: E501
# pylint: disable=line-too-long, missing-function-docstring
# pylint: disable=missing-param-doc,missing-return-doc,protected-access
"""Test waldiez_runner.client._tasks_api.*."""

import httpx
import pytest
from pytest_httpx import HTTPXMock

from waldiez_runner.client._auth import CustomAuth
from waldiez_runner.client._tasks_api import TasksAPIClient


@pytest.fixture(name="client")
def client_fixture(auth: CustomAuth) -> TasksAPIClient:
    """Return a new TasksAPIClient instance."""
    return TasksAPIClient(auth)


def test_configure(client: TasksAPIClient, auth: CustomAuth) -> None:
    """Test client configuration."""
    assert client._auth == auth
    assert client._auth.base_url == "http://localhost:8000"


def test_trigger_task(client: TasksAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test triggering a task."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks?input_timeout=10",
        json={"task_id": "12345"},
        status_code=200,
    )
    response = client.trigger_task(b"file_data", "test.txt", input_timeout=10)
    assert response == {"task_id": "12345"}


def test_get_task_status(client: TasksAPIClient, httpx_mock: HTTPXMock) -> None:
    """Test retrieving task status."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks/12345",
        json={"status": "completed"},
        status_code=200,
    )

    response = client.get_task_status("12345")
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
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks/12345",
        json={"status": "canceled"},
        status_code=200,
    )

    response = client.cancel_task("12345")
    assert response == {"status": "canceled"}


@pytest.mark.anyio
async def test_a_trigger_task(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test triggering a task asynchronously."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks?input_timeout=10",
        json={"task_id": "12345"},
        status_code=200,
    )

    response = await client.a_trigger_task(
        b"file_data", "test.txt", input_timeout=10
    )
    assert response == {"task_id": "12345"}


@pytest.mark.anyio
async def test_a_get_task_status(
    client: TasksAPIClient, httpx_mock: HTTPXMock
) -> None:
    """Test retrieving task status asynchronously."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks/12345",
        json={"status": "completed"},
        status_code=200,
    )

    response = await client.a_get_task_status("12345")
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
    # No assertion needed, just check if it raises an exception


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
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks/12345",
        json={"status": "canceled"},
        status_code=200,
    )

    response = await client.a_cancel_task("12345")
    assert response == {"status": "canceled"}


def test_invalid_client_config() -> None:
    """Test initializing the client without auth."""
    client = TasksAPIClient(auth=None)
    with pytest.raises(ValueError, match="Client is not configured"):
        client.trigger_task(b"file_data", "test.txt")


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
        client.trigger_task(b"file_data", "test.txt")


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
        await client.a_trigger_task(b"file_data", "test.txt")
