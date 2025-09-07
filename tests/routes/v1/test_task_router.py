# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-return-doc,missing-yield-doc
# pylint: disable=missing-param-doc,missing-raises-doc,unused-argument
"""Test waldiez_runner.routes.task_router."""

import hashlib
import json
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_200_OK, HTTP_204_NO_CONTENT

from tests.types import CreateTaskCallable
from waldiez_runner.config import Settings, SettingsManager
from waldiez_runner.dependencies.storage import LocalStorage
from waldiez_runner.main import get_app
from waldiez_runner.models.task import Task
from waldiez_runner.models.task_status import TaskStatus
from waldiez_runner.routes.v1.task_input_validation import (
    MAX_TASKS_ERROR,
    MAX_TASKS_PER_CLIENT,
)
from waldiez_runner.routes.v1.task_router import (  # type: ignore
    get_storage,
    validate_tasks_audience,
)
from waldiez_runner.schemas.client import ClientCreateResponse

VALID_EXTENSION = ".waldiez"
VALID_CONTENT_TYPE = "application/json"
ROOT_MODULE = "waldiez_runner.routes.v1"


@pytest.fixture(name="storage_service")
def storage_service_fixture(tmp_path: Path) -> LocalStorage:
    """Fixture for LocalStorage."""
    return LocalStorage(tmp_path)


@pytest.fixture(name="client_id")
def client_id_fixture(tasks_api_client: ClientCreateResponse) -> str:
    """Return a client ID."""
    return tasks_api_client.id


@pytest.fixture(name="client")
async def client_fixture(
    tasks_api_client: ClientCreateResponse,
    settings: Settings,
    storage_service: LocalStorage,
) -> AsyncGenerator[AsyncClient, None]:
    """Get the FastAPI test client."""

    async def get_valid_api_client_id_mock() -> str:
        """Mock get_valid_client_id."""
        return tasks_api_client.id

    def get_storage_mock() -> LocalStorage:
        """Mock get_storage."""
        return storage_service

    # pylint: disable=duplicate-code
    with patch.object(SettingsManager, "load_settings", return_value=settings):
        app = get_app()
        app.dependency_overrides[validate_tasks_audience] = (
            get_valid_api_client_id_mock
        )
        app.dependency_overrides[get_storage] = get_storage_mock
        async with LifespanManager(app, startup_timeout=10) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app),
                base_url="http://test/api/v1",
            ) as api_client:
                yield api_client


@pytest.fixture(name="kiq")
def kiq_fixture(
    mocker: MockerFixture, request: pytest.FixtureRequest
) -> AsyncMock:
    """Fixture to mock Taskiq task `kiq()` calls."""
    task_name = request.param  # e.g., "cancel_task_job", "delete_task_job"
    return mocker.patch(
        f"{ROOT_MODULE}.task_jobs.{task_name}.kiq",
        new_callable=AsyncMock,
    )


@pytest.mark.anyio
async def test_get_tasks(
    client: AsyncClient,
    async_session: AsyncSession,
    client_id: str,
    create_task: CreateTaskCallable,
) -> None:
    """Test getting tasks."""
    task, _ = await create_task(
        async_session,
        client_id=client_id,
        flow_id="flow123",
        status=TaskStatus.PENDING,
        filename="test",
    )

    response = await client.get("/tasks")

    assert response.status_code == HTTP_200_OK
    data_dict = response.json()
    data = data_dict["items"]
    assert len(data) == 1
    assert data[0]["id"] == str(task.id)


@pytest.mark.anyio
async def test_get_tasks_search(
    client: AsyncClient,
    async_session: AsyncSession,
    client_id: str,
    create_task: CreateTaskCallable,
) -> None:
    """Test getting tasks with search."""
    task, _ = await create_task(
        async_session,
        client_id=client_id,
        flow_id="flow123",
        status=TaskStatus.PENDING,
        filename="test_get_tasks_search",
    )

    response = await client.get(
        "/tasks", params={"search": "test_get_tasks_search"}
    )

    assert response.status_code == HTTP_200_OK
    data_dict = response.json()
    data = data_dict["items"]
    assert len(data) == 1
    assert data[0]["id"] == str(task.id)


@pytest.mark.anyio
async def test_get_tasks_search_no_results(
    client: AsyncClient,
) -> None:
    """Test getting tasks with search and no results."""
    response = await client.get(
        "/tasks", params={"search": "non_existent_task"}
    )

    assert response.status_code == HTTP_200_OK
    data_dict = response.json()
    data = data_dict["items"]
    assert len(data) == 0


# noinspection DuplicatedCode
@pytest.mark.anyio
async def test_get_tasks_sorted(
    client: AsyncClient,
    async_session: AsyncSession,
    client_id: str,
    create_task: CreateTaskCallable,
) -> None:
    """Test getting tasks with ordering."""
    task1, _ = await create_task(
        async_session,
        client_id=client_id,
        flow_id="flow123",
        status=TaskStatus.PENDING,
        filename="test_get_tasks_ordered_1",
    )
    task2, _ = await create_task(
        async_session,
        client_id=client_id,
        flow_id="flow123",
        status=TaskStatus.PENDING,
        filename="test_get_tasks_ordered_2",
    )

    response = await client.get(
        "/tasks", params={"order_by": "filename", "order_type": "desc"}
    )

    assert response.status_code == HTTP_200_OK
    data_dict = response.json()
    data = data_dict["items"]
    assert len(data) == 2
    assert data[0]["id"] == str(task2.id)
    assert data[1]["id"] == str(task1.id)

    response_2 = await client.get(
        "/tasks", params={"order_by": "filename", "order_type": "asc"}
    )
    assert response_2.status_code == HTTP_200_OK
    data_dict_2 = response_2.json()
    data_2 = data_dict_2["items"]
    assert len(data_2) == 2
    assert data_2[0]["id"] == str(task1.id)
    assert data_2[1]["id"] == str(task2.id)


@pytest.mark.anyio
@pytest.mark.parametrize("kiq", ["run_task_job"], indirect=True)
async def test_create_task(
    client: AsyncClient,
    async_session: AsyncSession,
    client_id: str,
    kiq: AsyncMock,
) -> None:
    """Test creating a task."""
    file_content = b'{"key": "value"}'
    file = {
        "file": (
            f"test_file{VALID_EXTENSION}",
            file_content,
            VALID_CONTENT_TYPE,
        )
    }
    env_vars = {
        "API_1_KEY": "test_api_key",
        "API_2_KEY": "test_api_key_2",
    }
    response = await client.post(
        "/tasks", files=file, params={"env_vars": json.dumps(env_vars)}
    )

    expected_content_md5 = hashlib.md5(
        file_content, usedforsecurity=False
    ).hexdigest()
    expected_filename_md5 = hashlib.md5(
        f"test_file{VALID_EXTENSION}".encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:8]
    expected_md5 = f"{expected_content_md5}-{expected_filename_md5}"
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["client_id"] == client_id
    assert data["status"] == "PENDING"
    assert data["flow_id"] == expected_md5

    task_in_db = await async_session.get(Task, data["id"])
    assert task_in_db is not None


@pytest.mark.anyio
async def test_create_task_invalid_file(
    client: AsyncClient,
) -> None:
    """Test creating a task with invalid file."""
    file = {"file": ("test_file", b"dummy content", "application/octet-stream")}

    response = await client.post("/tasks", files=file)

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid file type"}


@pytest.mark.anyio
async def test_create_task_active_flow_task(
    client: AsyncClient,
    async_session: AsyncSession,
    client_id: str,
    storage_service: LocalStorage,
) -> None:
    """Test creating a task with an active task with the same flow ID."""
    file_content = b'{"key": "value"}'
    file_name = f"test_file{VALID_EXTENSION}"
    flow_content_hash = hashlib.md5(
        file_content, usedforsecurity=False
    ).hexdigest()
    file_name_hash = hashlib.md5(
        file_name.encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:8]
    flow_hash = f"{flow_content_hash}-{file_name_hash}"
    task = Task(
        client_id=client_id,
        flow_id=flow_hash,
        status=TaskStatus.RUNNING,
        filename=file_name,
    )
    async_session.add(task)
    await async_session.commit()
    await async_session.refresh(task)

    task_folder_path = storage_service.root_dir / client_id / str(task.id)
    task_folder_path.mkdir(parents=True, exist_ok=True)
    (task_folder_path / file_name).write_text(file_content.decode())

    file = {
        "file": (
            file_name,
            file_content,
            VALID_CONTENT_TYPE,
        )
    }
    response = await client.post("/tasks", files=file)

    assert response.status_code == 400
    # pylint: disable=no-member
    assert response.json() == {
        "detail": (
            f"A task with the same file already exists. "
            f"Task ID: {task.id}, status: {task.get_status()}"
        )
    }


@pytest.mark.anyio
async def test_create_task_max_tasks(
    client: AsyncClient,
    async_session: AsyncSession,
    client_id: str,
) -> None:
    """Test creating a task when the client has reached the maximum tasks."""
    for _ in range(MAX_TASKS_PER_CLIENT):
        task = Task(
            client_id=client_id,
            flow_id="flow123",
            status=TaskStatus.PENDING,
            filename="test",
        )
        async_session.add(task)
    await async_session.commit()

    file_content = b'{"key": "value"}'
    file = {
        "file": (
            f"test_file{VALID_EXTENSION}",
            file_content,
            VALID_CONTENT_TYPE,
        )
    }
    response = await client.post("/tasks", files=file)

    assert response.status_code == 400
    assert response.json() == {"detail": MAX_TASKS_ERROR}


@pytest.mark.anyio
async def test_get_task(
    client: AsyncClient,
    async_session: AsyncSession,
    client_id: str,
) -> None:
    """Test getting a task."""
    task = Task(
        client_id=client_id,
        flow_id="flow123",
        status=TaskStatus.PENDING,
        filename="test",
    )
    async_session.add(task)
    await async_session.commit()
    await async_session.refresh(task)

    response = await client.get(f"/tasks/{task.id}")

    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["id"] == str(task.id)


@pytest.mark.anyio
async def test_get_task_not_found(
    client: AsyncClient,
) -> None:
    """Test getting a non-existent task."""
    response = await client.get("/tasks/123")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_cancel_task(
    client: AsyncClient,
    async_session: AsyncSession,
    client_id: str,
) -> None:
    """Test cancelling a task."""
    task = Task(
        client_id=client_id,
        flow_id="flow123",
        status=TaskStatus.PENDING,
        filename="test",
    )
    async_session.add(task)
    await async_session.commit()
    await async_session.refresh(task)

    # let's patch the task_cancellation publisher to avoid any issues
    # with redis / FakeRedis
    # we handle it in smoke tests and (should! handle it) e2e tests
    with patch(
        f"{ROOT_MODULE}.task_router.publish_task_cancellation",
        new_callable=AsyncMock,
    ):
        response = await client.post(f"/tasks/{task.id}/cancel")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["id"] == str(task.id)
        assert data["status"] == TaskStatus.CANCELLED.value

        await async_session.refresh(task)
        task_in_db = await async_session.get(Task, str(task.id))
        assert task_in_db is not None
        assert task_in_db.status == TaskStatus.CANCELLED


@pytest.mark.anyio
async def test_cancel_task_not_found(
    client: AsyncClient,
) -> None:
    """Test cancelling a non-existent task."""
    response = await client.post("/tasks/123/cancel")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_cancel_task_invalid_status(
    client: AsyncClient,
    async_session: AsyncSession,
    client_id: str,
) -> None:
    """Test cancelling a task with an invalid status."""
    task = Task(
        client_id=client_id,
        flow_id="flow123",
        status=TaskStatus.COMPLETED,
        filename="test",
    )
    async_session.add(task)
    await async_session.commit()
    await async_session.refresh(task)

    response = await client.post(f"/tasks/{task.id}/cancel")

    assert response.status_code == 400
    # pylint: disable=no-member
    assert response.json() == {
        "detail": f"Cannot cancel task with status {task.get_status()}"
    }


@pytest.mark.anyio
@pytest.mark.parametrize("kiq", ["delete_task_job"], indirect=True)
async def test_delete_task(
    client: AsyncClient,
    async_session: AsyncSession,
    storage_service: LocalStorage,
    client_id: str,
    kiq: AsyncMock,
) -> None:
    """Test deleting a task."""
    task = Task(
        client_id=client_id,
        flow_id="flow123",
        status=TaskStatus.COMPLETED,
        filename="test",
    )
    async_session.add(task)
    await async_session.commit()
    await async_session.refresh(task)

    task_folder_path = storage_service.root_dir / client_id / str(task.id)
    task_folder_path.mkdir(parents=True, exist_ok=True)
    (task_folder_path / "file1.txt").write_text("test")
    response = await client.delete(f"/tasks/{task.id}")

    assert response.status_code == HTTP_204_NO_CONTENT

    await async_session.refresh(task)
    task_in_db = await async_session.get(Task, task.id)
    assert task_in_db is None or (
        task_in_db is not None and task_in_db.is_deleted
    )


@pytest.mark.anyio
async def test_delete_task_not_found(
    client: AsyncClient,
) -> None:
    """Test deleting a non-existent task."""
    response = await client.delete("/tasks/123")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_delete_active_task(
    client: AsyncClient,
    async_session: AsyncSession,
    client_id: str,
) -> None:
    """Test deleting an active task."""
    task = Task(
        client_id=client_id,
        flow_id="flow123",
        status=TaskStatus.RUNNING,
        filename="test",
    )
    async_session.add(task)
    await async_session.commit()
    await async_session.refresh(task)

    response = await client.delete(f"/tasks/{task.id}")

    assert response.status_code == 400


# noinspection DuplicatedCode
@pytest.mark.anyio
async def test_download_task(
    client: AsyncClient,
    async_session: AsyncSession,
    client_id: str,
    storage_service: LocalStorage,
) -> None:
    """Test downloading a task."""
    task = Task(
        client_id=client_id,
        flow_id="flow123",
        status=TaskStatus.COMPLETED,
        results={"test": "result"},
        filename="test",
    )
    async_session.add(task)
    await async_session.commit()
    await async_session.refresh(task)

    task_folder_path = storage_service.root_dir / client_id / str(task.id)
    task_folder_path.mkdir(parents=True, exist_ok=True)
    (task_folder_path / "file1.txt").write_text("test")

    response = await client.get(f"/tasks/{task.id}/download")

    assert response.status_code == HTTP_200_OK
    assert response.headers["Content-Type"] in (
        "application/zip",
        "application/x-zip-compressed",
    )
    assert (
        response.headers["content-disposition"]
        == f"attachment; filename={task.id}.zip"
    )


@pytest.mark.anyio
async def test_download_task_not_found(
    client: AsyncClient,
) -> None:
    """Test downloading a non-existent task."""
    response = await client.get("/tasks/123/download")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}
