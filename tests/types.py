# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
# pyright: reportReturnType=false
"""Types for tests."""

from collections.abc import Coroutine
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from waldiez_runner.models.client import Client
from waldiez_runner.models.task import Task
from waldiez_runner.models.task_status import TaskStatus
from waldiez_runner.schemas.client import ClientCreateResponse
from waldiez_runner.schemas.task import TaskResponse


# pylint: disable=too-few-public-methods
class CreateClientCallable(Protocol):
    """Callable to create a client."""

    def __call__(
        self,
        session: AsyncSession,
        audience: str | None = None,
        name: str | None = None,
        description: str | None = None,
        client_id: str | None = None,
    ) -> Coroutine[Any, Any, tuple[Client, ClientCreateResponse]]:
        """Callable to create a client.

        Parameters
        ----------
        session : AsyncSession
            The database session.
        audience : str | None
            The audience of the client.
        name : str | None
            The name of the client.
        description : str | None
            The description of the client.
        client_id : str | None
            The client ID.

        Returns
        -------
        Tuple[Client, ClientCreateResponse]
            The created client and the response (includes the plain secret).
        """


class CreateTaskCallable(Protocol):
    """Callable to create a task."""

    def __call__(
        self,
        session: AsyncSession,
        client_id: str,
        flow_id: str = "flow1",
        filename: str = "file1.waldiez",
        status: TaskStatus = TaskStatus.PENDING,
        input_timeout: int = 180,
    ) -> Coroutine[Any, Any, tuple[Task, TaskResponse]]:
        """Callable to create a task.

        Parameters
        ----------
        session : AsyncSession
            The database session.
        client : Client
            The client.
        task_in : TaskCreate
            The task data.

        Returns
        -------
        tuple[Task, TaskResponse]
            The created task and the response.
        """
