# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-return-doc
# pylint: disable=protected-access,unused-argument
"""Test waldiez_runner.client._tasks_client.*."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from waldiez_runner.client.auth import Auth
from waldiez_runner.client.tasks_client import TasksClient


@pytest.fixture(name="tasks_client")
def tasks_client_fixture(auth: Auth) -> TasksClient:
    """Return a new TasksClient instance."""
    client = TasksClient()
    assert auth.base_url is not None
    assert auth.client_id is not None
    assert auth.client_secret is not None
    client.configure(
        base_url=auth.base_url,
        client_id=auth.client_id,
        client_secret=auth.client_secret,
    )
    return client


def test_configure_sets_sub_clients(tasks_client: TasksClient) -> None:
    """Test that configure sets the sub-clients."""
    assert tasks_client.tasks is not None
    assert tasks_client.ws_sync is not None
    assert tasks_client.ws_async is not None


def test_ensure_configured_raises() -> None:
    """Test _ensure_configured raises ValueError if not configured."""
    client = TasksClient()
    with pytest.raises(ValueError):
        client._ensure_configured()


def test_list_tasks(httpx_mock: HTTPXMock, tasks_client: TasksClient) -> None:
    """Test listing tasks."""
    response_dict = {"items": [], "total": 0, "page": 1, "size": 50, "pages": 1}
    httpx_mock.add_response(
        method="GET",
        url=f"{tasks_client.base_url}/api/v1/tasks",
        json=response_dict,
    )
    assert tasks_client.list_tasks().model_dump() == response_dict


def test_delete_all_tasks(
    httpx_mock: HTTPXMock, tasks_client: TasksClient
) -> None:
    """Test deleting all tasks."""
    url = f"{tasks_client.base_url}/api/v1/tasks?force=false"
    httpx_mock.add_response(
        method="DELETE",
        url=url,
        status_code=204,
    )
    tasks_client.delete_tasks()


def test_force_delete_all_tasks(
    httpx_mock: HTTPXMock,
    tasks_client: TasksClient,
) -> None:
    """Test force deleting all tasks."""
    httpx_mock.add_response(
        method="DELETE",
        url=f"{tasks_client.base_url}/api/v1/tasks?force=true",
        status_code=204,
    )
    tasks_client.delete_tasks(force=True)


def test_create_task(httpx_mock: HTTPXMock, tasks_client: TasksClient) -> None:
    """Test creating a task."""
    httpx_mock.add_response(
        method="POST",
        url=f"{tasks_client.base_url}/api/v1/tasks?input_timeout=10",
        json={
            "id": "123",
            "created_at": "2023-10-01T00:00:00Z",
            "updated_at": "2023-10-01T00:00:00Z",
            "client_id": "client_id",
            "flow_id": "flow_id",
            "filename": "file.txt",
            "status": "RUNNING",
            "input_timeout": 10,
            "input_request_id": None,
            "results": None,
        },
    )
    resp = tasks_client.create_task(
        {"file_data": b"data", "file_name": "file.txt", "input_timeout": 10}
    ).model_dump()
    assert resp["id"] == "123"


def test_send_user_input_ws(
    mocker: MockerFixture, tasks_client: TasksClient
) -> None:
    """Test sending user input via WebSocket."""
    mock_send = mocker.patch.object(tasks_client.ws_sync, "send")
    mocker.patch.object(tasks_client.ws_sync, "is_listening", return_value=True)
    tasks_client.send_user_input(
        {
            "task_id": "task1",
            "request_id": "req1",
            "data": "input",
        }
    )
    mock_send.assert_called_once()


def test_send_user_input_rest_fallback(
    mocker: MockerFixture, httpx_mock: HTTPXMock, tasks_client: TasksClient
) -> None:
    """Test sending user input via REST fallback."""
    httpx_mock.add_response(
        method="POST",
        url=f"{tasks_client.base_url}/api/v1/tasks/task1/input",
        status_code=204,
    )
    mocker.patch.object(
        tasks_client.ws_sync, "is_listening", return_value=False
    )
    tasks_client.send_user_input(
        {
            "task_id": "task1",
            "request_id": "req1",
            "data": "input",
        }
    )


def test_is_listening_false() -> None:
    """Test is_listening returns False."""
    client = TasksClient()
    client.ws_sync = None
    assert client.is_listening() is False


def test_start_ws_listener_not_configured() -> None:
    """Test start_ws_listener raises ValueError if not configured."""
    client = TasksClient()
    client.ws_sync = None
    with pytest.raises(ValueError):
        client.start_ws_listener("t", lambda m: None)


def test_client_start_stop_ws_sync(
    tasks_client: TasksClient, mocker: MockerFixture
) -> None:
    """Test client start and stop WebSocket listener."""
    mocked_listen = mocker.patch.object(
        tasks_client.ws_sync, "listen", autospec=True
    )
    mocked_stop = mocker.patch.object(
        tasks_client.ws_sync, "stop", autospec=True
    )

    tasks_client.start_ws_listener("task1", lambda m: None)
    tasks_client.stop_ws_listener()

    mocked_listen.assert_called_once()
    mocked_stop.assert_called_once()


def test_stop_ws_listener(tasks_client: TasksClient) -> None:
    """Test stop_ws_listener stops the listener."""
    tasks_client.stop_ws_listener()
    assert tasks_client.ws_sync is None


@pytest.mark.anyio
async def test_a_send_user_input_ws(
    mocker: MockerFixture, tasks_client: TasksClient
) -> None:
    """Test sending user input via WebSocket asynchronously."""
    mock_send = mocker.patch.object(
        tasks_client.ws_async, "send", new_callable=AsyncMock
    )
    mocker.patch.object(
        tasks_client.ws_async, "is_listening", return_value=True
    )
    await tasks_client.a_send_user_input(
        {
            "task_id": "task1",
            "request_id": "req1",
            "data": "input",
        }
    )
    mock_send.assert_awaited_once()


@pytest.mark.anyio
async def test_start_ws_async_listener_not_configured() -> None:
    """Test start_ws_async_listener raises ValueError if not configured."""
    client = TasksClient()
    client.ws_async = None
    with pytest.raises(ValueError):
        await client.start_ws_async_listener("task1", on_message=AsyncMock())


@pytest.mark.anyio
async def test_stop_ws_async_listener(
    tasks_client: TasksClient, mocker: MockerFixture
) -> None:
    """Test stop_ws_async_listener stops the listener."""
    mock_stop = mocker.patch.object(
        tasks_client.ws_async, "stop", new_callable=AsyncMock
    )
    await tasks_client.stop_ws_async_listener()
    mock_stop.assert_awaited_once()
    assert tasks_client.ws_async is None


def test_close_calls_ws_sync_and_ws_async_stop(mocker: MockerFixture) -> None:
    """Test close calls ws_sync.stop and ws_async.stop."""
    client = TasksClient()
    mock_sync = mocker.MagicMock()
    mock_async = mocker.AsyncMock()
    client.ws_sync = mock_sync
    client.ws_async = mock_async

    client.close()
    mock_sync.stop.assert_called_once()
    mock_async.stop.assert_called_once()


def test_close_falls_back_to_asyncio_run(mocker: MockerFixture) -> None:
    """Test close falls back to asyncio.run if get_running_loop raises."""
    client = TasksClient()
    mock_ws_async = mocker.Mock()
    mock_ws_async.stop = mocker.Mock()
    client.ws_async = mock_ws_async

    mocker.patch("asyncio.get_running_loop", side_effect=RuntimeError)
    mock_run = mocker.patch("asyncio.run")
    client.close()

    mock_run.assert_called_once()


def test_configure_skips_tasks_ws_setup() -> None:
    """Test configure skips tasks and ws setup if no client_id/secret."""
    client = TasksClient()
    client.configure(
        base_url="http://localhost",
        client_id="",
        client_secret="",  # nosemgrep # nosec
    )
    assert client.tasks is None
    assert client.ws_sync is None
    assert client.ws_async is None


def test_send_user_input_fallback_on_ws_error(
    httpx_mock: HTTPXMock,
    auth: Auth,
) -> None:
    """Test sending user input falls back on WebSocket error."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks/task1/input",
        status_code=204,
    )

    client = TasksClient()
    client.configure(
        "http://localhost:8000",
        client_id=auth.client_id,  # type: ignore
        client_secret=auth.client_secret,  # type: ignore
    )
    client.ws_sync.is_listening = MagicMock(return_value=True)  # type: ignore
    client.ws_sync.send = MagicMock(  # type: ignore
        side_effect=Exception("fail"),
    )

    client.send_user_input(
        {
            "task_id": "task1",
            "request_id": "req123",
            "data": "hello",
        }
    )
    client.ws_sync.send.assert_called_once()  # type: ignore


def test_start_ws_listener_exits_if_already_listening(
    mocker: MockerFixture,
) -> None:
    """Test start_ws_listener exits if already listening."""
    client = TasksClient()
    client.ws_sync = mocker.Mock()
    client.ws_sync.is_listening.return_value = True  # type: ignore

    client.start_ws_listener("task1", lambda _: None)
    client.ws_sync.listen.assert_not_called()  # type: ignore


def test_cancel_task(
    httpx_mock: HTTPXMock,
    auth: Auth,
) -> None:
    """Test canceling a task."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks/task1/cancel",
        json={
            "id": "task1",
            "created_at": "2023-10-01T00:00:00Z",
            "updated_at": "2023-10-01T00:00:00Z",
            "client_id": "client_id",
            "flow_id": "flow_id",
            "filename": "file.txt",
            "status": "CANCELLED",
            "input_request_id": None,
            "input_timeout": 10,
        },
        status_code=200,
    )
    client = TasksClient()
    client.configure("http://localhost:8000", "id", "secret")
    response = client.cancel_task("task1")
    assert response.model_dump()["status"] == "CANCELLED"


def test_delete_task(
    httpx_mock: HTTPXMock,
    auth: Auth,
) -> None:
    """Test deleting a task."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks/task1",
        status_code=204,
    )
    client = TasksClient()
    client.configure("http://localhost:8000", "id", "secret")
    client.delete_task("task1")


def test_force_delete_task(
    httpx_mock: HTTPXMock,
    auth: Auth,
) -> None:
    """Test force deleting a task."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks/task1?force=true",
        status_code=204,
    )
    client = TasksClient()
    client.configure("http://localhost:8000", "id", "secret")
    client.delete_task("task1", force=True)


def test_get_task_status(
    httpx_mock: HTTPXMock,
    auth: Auth,
) -> None:
    """Test retrieving task status."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks/task1",
        json={
            "id": "task1",
            "created_at": "2023-10-01T00:00:00Z",
            "updated_at": "2023-10-01T00:00:00Z",
            "client_id": "client_id",
            "flow_id": "flow_id",
            "filename": "file.txt",
            "status": "RUNNING",
            "input_timeout": 10,
            "input_request_id": None,
            "results": None,
        },
        status_code=200,
    )
    client = TasksClient()
    client.configure("http://localhost:8000", "id", "secret")
    status = client.get_task_status("task1").model_dump()
    assert status["status"] == "RUNNING"


def test_download_task_results(
    httpx_mock: HTTPXMock,
    auth: Auth,
) -> None:
    """Test downloading task results (sync)."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks/task1/download",
        content=b"zipdata",
    )
    client = TasksClient()
    client.configure("http://localhost:8000", "id", "secret")
    data = client.download_task_results("task1")
    assert data == b"zipdata"


def test_send_user_input_fallback_to_rest(
    mocker: MockerFixture, httpx_mock: HTTPXMock, auth: Auth
) -> None:
    """Test REST fallback if WebSocket is not active (sync)."""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/api/v1/tasks/task1/input",
        status_code=204,
    )
    client = TasksClient()
    client.configure("http://localhost:8000", "id", "secret")
    mocker.patch.object(client.ws_sync, "is_listening", return_value=False)
    client.send_user_input(
        {
            "task_id": "task1",
            "request_id": "req-id",
            "data": "user input",
        }
    )


@pytest.mark.asyncio
async def test_start_ws_async_listener_triggers_listen(
    tasks_client: TasksClient,
) -> None:
    """Test start_ws_async_listener triggers listen."""
    mock_listen = AsyncMock()
    tasks_client.a_is_listening = AsyncMock(return_value=False)  # type: ignore
    tasks_client.ws_async.listen = mock_listen  # type: ignore

    await tasks_client.start_ws_async_listener("task1", on_message=AsyncMock())

    mock_listen.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_ws_async_listener_exits_if_already_listening() -> None:
    """Test start_ws_async_listener exits if already listening."""
    client = TasksClient()
    client.ws_async = AsyncMock()
    client.a_is_listening = AsyncMock(return_value=True)  # type: ignore

    await client.start_ws_async_listener("task1", on_message=AsyncMock())
    client.ws_async.listen.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_is_listening_no_ws() -> None:
    """Test a_is_listening returns False if no ws."""
    client = TasksClient()
    client.ws_async = None
    assert await client.a_is_listening() is False


@pytest.mark.anyio
async def test_a_list_tasks(
    httpx_mock: HTTPXMock,
    auth: Auth,
) -> None:
    """Test listing tasks asynchronously."""
    response_dict = {
        "items": [],
        "total": 0,
        "page": 1,
        "size": 50,
        "pages": 1,
    }
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8000/api/v1/tasks",
        json=response_dict,
    )
    client = TasksClient()
    client.configure("http://localhost:8000", "id", "secret")
    response = await client.a_list_tasks()
    tasks = response.model_dump()
    assert tasks == response_dict


@pytest.mark.anyio
async def test_a_delete_task(
    httpx_mock: HTTPXMock,
    auth: Auth,
) -> None:
    """Test deleting a task asynchronously."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks/task1",
        status_code=204,
    )
    client = TasksClient()
    client.configure("http://localhost:8000", "id", "secret")
    await client.a_delete_task("task1")


@pytest.mark.anyio
async def test_a_force_delete_task(
    httpx_mock: HTTPXMock,
    auth: Auth,
) -> None:
    """Test force deleting a task asynchronously."""
    httpx_mock.add_response(
        method="DELETE",
        url="http://localhost:8000/api/v1/tasks/task1?force=true",
        status_code=204,
    )
    client = TasksClient()
    client.configure("http://localhost:8000", "id", "secret")
    await client.a_delete_task("task1", force=True)


@pytest.mark.anyio
async def test_a_delete_all_tasks(
    httpx_mock: HTTPXMock,
    tasks_client: TasksClient,
) -> None:
    """Test deleting all tasks asynchronously."""
    httpx_mock.add_response(
        method="DELETE",
        url=f"{tasks_client.base_url}/api/v1/tasks?force=false",
        status_code=204,
    )
    await tasks_client.a_delete_tasks()


@pytest.mark.anyio
async def test_a_force_delete_all_tasks(
    httpx_mock: HTTPXMock,
    tasks_client: TasksClient,
) -> None:
    """Test force deleting all tasks asynchronously."""
    httpx_mock.add_response(
        method="DELETE",
        url=f"{tasks_client.base_url}/api/v1/tasks?force=true",
        status_code=204,
    )
    await tasks_client.a_delete_tasks(force=True)


@pytest.mark.anyio
async def test_a_cancel_task(
    httpx_mock: HTTPXMock,
    tasks_client: TasksClient,
) -> None:
    """Test canceling a task asynchronously."""
    httpx_mock.add_response(
        method="POST",
        url=f"{tasks_client.base_url}/api/v1/tasks/task1/cancel",
        json={
            "id": "task1",
            "created_at": "2023-10-01T00:00:00Z",
            "updated_at": "2023-10-01T00:00:00Z",
            "client_id": "client_id",
            "flow_id": "flow_id",
            "filename": "file.txt",
            "status": "CANCELLED",
            "input_timeout": 10,
            "input_request_id": None,
            "results": None,
        },
        status_code=200,
    )
    response = await tasks_client.a_cancel_task("task1")
    assert response.model_dump()["status"] == "CANCELLED"


@pytest.mark.anyio
async def test_a_download_task_results(
    httpx_mock: HTTPXMock,
    tasks_client: TasksClient,
) -> None:
    """Test downloading task results (async)."""
    httpx_mock.add_response(
        method="GET",
        url=f"{tasks_client.base_url}/api/v1/tasks/task1/download",
        content=b"zipdata",
    )
    data = await tasks_client.a_download_task_results("task1")
    assert data == b"zipdata"


@pytest.mark.anyio
async def test_a_get_task_status(
    httpx_mock: HTTPXMock,
    tasks_client: TasksClient,
) -> None:
    """Test getting task status asynchronously."""
    httpx_mock.add_response(
        method="GET",
        url=f"{tasks_client.base_url}/api/v1/tasks/task1",
        json={
            "id": "task1",
            "created_at": "2023-10-01T00:00:00Z",
            "updated_at": "2023-10-01T00:00:00Z",
            "client_id": "client_id",
            "flow_id": "flow_id",
            "filename": "file.txt",
            "status": "RUNNING",
            "input_timeout": 10,
            "input_request_id": None,
            "results": None,
        },
    )
    response = await tasks_client.a_get_task_status("task1")
    task = response.model_dump()
    assert task["status"] == "RUNNING"


@pytest.mark.anyio
async def test_a_create_task(
    httpx_mock: HTTPXMock,
    tasks_client: TasksClient,
) -> None:
    """Test triggering a task asynchronously."""
    httpx_mock.add_response(
        method="POST",
        url=f"{tasks_client.base_url}/api/v1/tasks?input_timeout=10",
        json={
            "id": "12345",
            "created_at": "2023-10-01T00:00:00Z",
            "updated_at": "2023-10-01T00:00:00Z",
            "client_id": "client_id",
            "flow_id": "flow_id",
            "filename": "file.txt",
            "status": "PENDING",
            "input_timeout": 10,
            "input_request_id": None,
            "results": None,
        },
        status_code=200,
    )
    response = await tasks_client.a_create_task(
        {
            "file_data": b"data",
            "file_name": "test.txt",
            "input_timeout": 10,
        }
    )
    task = response.model_dump()
    assert task["id"] == "12345"


@pytest.mark.asyncio
async def test_client_start_stop_ws_async(
    mocker: MockerFixture,
    tasks_client: TasksClient,
) -> None:
    """Test client start and stop WebSocket listener."""

    mocked_listen = mocker.patch.object(
        tasks_client.ws_async, "listen", autospec=True
    )
    mocked_stop = mocker.patch.object(
        tasks_client.ws_async, "stop", autospec=True
    )

    await tasks_client.start_ws_async_listener(
        "task1", lambda m: asyncio.sleep(0)
    )
    await tasks_client.aclose()

    mocked_listen.assert_called_once()
    mocked_stop.assert_called_once()


@pytest.mark.anyio
async def test_a_send_user_input_fallback_to_rest(
    mocker: MockerFixture, httpx_mock: HTTPXMock, tasks_client: TasksClient
) -> None:
    """Test REST fallback if WebSocket is not active (async)."""
    httpx_mock.add_response(
        method="POST",
        url=f"{tasks_client.base_url}/api/v1/tasks/task1/input",
        status_code=204,
    )
    mocker.patch.object(
        tasks_client.ws_async, "is_listening", return_value=False
    )
    await tasks_client.a_send_user_input(
        {
            "task_id": "task1",
            "request_id": "req-id",
            "data": "user input",
        }
    )
