# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pylint: disable=import-outside-toplevel,protected-access,unused-argument
# pylint: disable=missing-return-doc,missing-yield-doc,missing-param-doc
"""Shared fixtures for tests."""

import os
import secrets
import shutil
import uuid
from pathlib import Path
from typing import AsyncGenerator, Generator, Tuple
from unittest.mock import patch

import fakeredis
import pytest
from pytest_httpx import HTTPXMock
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tests.types import CreateClientCallable, CreateTaskCallable
from waldiez_runner.client.auth import Auth
from waldiez_runner.config import Settings, SettingsManager
from waldiez_runner.models import Base, Client, Task, TaskStatus
from waldiez_runner.schemas.client import ClientCreate, ClientCreateResponse
from waldiez_runner.schemas.task import TaskCreate, TaskResponse
from waldiez_runner.services import ClientService, TaskService

TEST_DOT_ENV_PATH = Path(".test_env")
DOT_ENV_PATH_DOTTED = "waldiez_runner.config.settings.DOT_ENV_PATH"
ENV_KEY_PREFIX = "WALDIEZ_RUNNER_"
HERE = Path(__file__).parent
ROOT_DIR = HERE.parent
DB_PATH = ROOT_DIR / f"{ENV_KEY_PREFIX.lower()}test.db"
DB_PATH.unlink(missing_ok=True)
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"


@pytest.fixture(scope="function", autouse=True)
def reset_settings_and_env() -> Generator[None, None, None]:
    """Automatically reset SettingsManager before each test."""
    SettingsManager.reset_settings()
    os.environ[f"{ENV_KEY_PREFIX}TESTING"] = "1"
    for key in os.environ:
        if key.startswith(ENV_KEY_PREFIX) and key != f"{ENV_KEY_PREFIX}TESTING":
            os.environ.pop(key, "")
    yield
    SettingsManager.reset_settings()
    os.environ[f"{ENV_KEY_PREFIX}TESTING"] = "1"


def _ensure_keys() -> None:
    """Ensure secret_key, client_id and client_secret are set."""
    # in case a .env does not exist, or the keys are not set
    special_keys = (
        "secret_key",
        "local_client_id",
        "local_client_secret",
    )
    for key in special_keys:
        env_key = f"{ENV_KEY_PREFIX}{key.upper()}"
        if os.environ.get(env_key) is None:
            length = 32 if key == "local_client_id" else 64
            os.environ[env_key] = secrets.token_hex(length)


@pytest.fixture(autouse=True, scope="session", name="dot_env_path")
def dot_env_path_fixture() -> Generator[Path, None, None]:
    """Backup and restore the .env file before and after the test session."""
    # make sure a .env file exists
    os.environ[f"{ENV_KEY_PREFIX}TESTING"] = "1"
    dot_env_path = HERE.parent / ".env"
    if not dot_env_path.exists():
        _ensure_keys()
        settings = SettingsManager.load_settings(force_reload=True)
        settings.save()
    dot_env_path = HERE.parent / ".env"
    shutil.move(dot_env_path, dot_env_path.with_suffix(".bak"))
    with patch(DOT_ENV_PATH_DOTTED, TEST_DOT_ENV_PATH):
        yield TEST_DOT_ENV_PATH
        dot_env_path = HERE.parent / ".env"
        if dot_env_path.exists():
            dot_env_path.unlink()
        dot_env_bak = dot_env_path.with_suffix(".bak")
        if dot_env_bak.exists():
            shutil.move(dot_env_bak, dot_env_path)
        if TEST_DOT_ENV_PATH.exists():
            TEST_DOT_ENV_PATH.unlink()


@pytest.fixture(name="settings")
def settings_fixture() -> Settings:
    """Fixture to create a Settings instance."""
    settings = Settings(
        redis=False,
        redis_url=None,
        postgres=False,
        trusted_hosts=["test"],
        trusted_origins=["http://test"],
        db_url=DATABASE_URL,
    )
    return settings


@pytest.fixture(name="db_tables", scope="session", autouse=True)
async def db_tables_fixture() -> AsyncGenerator[None, None]:
    """Create the database tables before the test session."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
        except OperationalError:  # tables already exist
            pass
    yield


@pytest.fixture(name="async_session")
async def async_session_fixture() -> AsyncGenerator[AsyncSession, None]:
    """Fixture for an async session."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session_maker() as session:
        yield session


@pytest.fixture(name="fake_redis")
def fake_redis_fixture() -> fakeredis.FakeRedis:
    """Fake Redis client fixture."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture(name="a_fake_redis")
def a_fake_redis_fixture() -> fakeredis.aioredis.FakeRedis:
    """Fake async Redis client fixture."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture(name="auth")
def auth_fixture(httpx_mock: HTTPXMock) -> Auth:
    """Return a new CustomAuth instance."""
    auth = Auth()
    auth.configure(
        "client_id", "client_secret", base_url="http://localhost:8000"
    )
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8000/auth/token",
        json={
            "access_token": "valid_access_token",
            "token_type": "bearer",
            "expires_in": 3600,
            "refresh_token": "valid_refresh_token",
            "refresh_expires_in": 86400,
        },
        status_code=200,
        is_optional=True,
        is_reusable=True,
    )
    return auth


async def _create_client(
    session: AsyncSession,
    audience: str,
    name: str = "Test Client",
    description: str | None = None,
    client_id: str | None = None,
) -> Tuple[Client, ClientCreateResponse]:
    """Create a client."""
    if description is None:
        audience_parts = audience.split("-")
        if len(audience_parts) == 1:
            description = audience_parts[0].capitalize() + " API"
        else:
            # tasks-api -> Tasks API
            description = (
                audience_parts[0].capitalize() + audience_parts[1].upper()
            )
    client_create = ClientCreate(
        name=name,
        client_id=client_id or str(uuid.uuid4()),
        description=description,
        audience=audience,
    )
    response = await ClientService.create_client(
        session=session,
        client_create=client_create,
    )
    client = await ClientService.get_client_in_db(
        session=session,
        client_id=response.id,
    )
    if client is None:
        raise ValueError("Client not found")
    return client, response


async def _delete_client(
    async_session: AsyncSession,
    client: Client,
) -> None:
    """Delete a client."""
    async with async_session:
        await async_session.delete(client)
        await async_session.commit()


@pytest.fixture(name="create_client")
def client_factory() -> CreateClientCallable:
    """Fixture to create a client.

    Returns
    -------
    Callable
        A callable that takes a session and returns a client and a response.
        The callable takes the following parameters:
        - session: The database session.
        - name: The name of the client.
        - description: The description of the client.
        - audience: The audience of the client.
        - client_id: The client ID of the client.
    """

    async def _create(
        session: AsyncSession,
        audience: str | None = None,
        name: str | None = None,
        description: str | None = None,
        client_id: str | None = None,
    ) -> Tuple[Client, ClientCreateResponse]:
        """Create a client."""
        if audience is None:
            audience = "tasks-api"
        if name is None:
            name = "Test Client"
        return await _create_client(
            session=session,
            audience=audience,
            name=name,
            description=description,
            client_id=client_id,
        )

    return _create


@pytest.fixture(name="tasks_api_client")
async def tasks_api_client_fixture(
    async_session: AsyncSession,
) -> AsyncGenerator[ClientCreateResponse, None]:
    """Fixture to create a client_id for the tasks API."""
    client, response = await _create_client(async_session, "tasks-api")
    yield response
    await _delete_client(async_session, client)


@pytest.fixture(name="clients_api_client")
async def clients_api_client_fixture(
    async_session: AsyncSession,
) -> AsyncGenerator[ClientCreateResponse, None]:
    """Fixture to create a client_id for the clients API."""
    client, response = await _create_client(async_session, "clients-api")
    yield response
    await _delete_client(async_session, client)


async def _create_task(
    session: AsyncSession,
    client_id: str,
    flow_id: str = "flow1",
    filename: str = "file1.waldiez",
    status: TaskStatus = TaskStatus.PENDING,
    input_timeout: int = 180,
) -> Tuple[Task, TaskResponse]:
    """Create a task."""
    task_create = TaskCreate(
        client_id=client_id,
        flow_id=flow_id,
        filename=filename,
        input_timeout=input_timeout,
    )
    task = await TaskService.create_task(
        session=session,
        task_create=task_create,
    )
    if status != task.status:
        task.status = status
        await session.commit()
        await session.refresh(task)
    return task, TaskResponse.model_validate(task)


@pytest.fixture(name="create_task")
def create_task_fixture() -> CreateTaskCallable:
    """Fixture to create a task.

    Returns
    -------
    Callable
        A callable that takes a session and returns a task and a response.
        The callable takes the following parameters:
        - session: The database session.
        - client_id: The client ID of the task.
        - flow_id: The flow ID of the task.
        - filename: The filename of the task.
        - status: The status of the task.
        - input_timeout: The input timeout of the task.
    """

    async def _create(
        session: AsyncSession,
        client_id: str,
        flow_id: str = "flow1",
        filename: str = "file1.waldiez",
        status: TaskStatus = TaskStatus.PENDING,
        input_timeout: int = 180,
    ) -> Tuple[Task, TaskResponse]:
        """Create a task."""
        return await _create_task(
            session=session,
            client_id=client_id,
            flow_id=flow_id,
            filename=filename,
            status=status,
            input_timeout=input_timeout,
        )

    return _create
