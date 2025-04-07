# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Other routes like health check, robots.txt, and status."""

import psutil
from fastapi import APIRouter, Depends, FastAPI, Response
from sqlalchemy.ext.asyncio import AsyncSession

from waldiez_runner.config import ServerStatus
from waldiez_runner.dependencies import VALID_AUDIENCES, get_client_id, get_db
from waldiez_runner.services import TaskService

router = APIRouter()

validate_clients_audience = get_client_id(*VALID_AUDIENCES)


@router.get("/health", include_in_schema=False)
@router.get("/health/", include_in_schema=False)
@router.get("/healthz", include_in_schema=False)
@router.get("/healthz/", include_in_schema=False)
async def health() -> Response:
    """Health check route.

    Returns
    -------
    Response
        The response
    """
    return Response(
        content="OK",
        status_code=200,
    )


@router.get("/robots.txt", include_in_schema=False)
async def robots() -> Response:
    """Robots route.

    Returns
    -------
    Response
        The response
    """
    return Response(
        content="User-agent: *\nDisallow: /",
        media_type="text/plain",
    )


def add_status_route(app: FastAPI, max_jobs: int) -> None:
    """Add the status route to the application.

    Parameters
    ----------
    app : APIRouter
        The application
    max_jobs : int
        The maximum number of jobs
    """

    @app.get(
        "/status",
        tags=["Status"],
        summary="Check application status",
        description="Returns application health status, database status, etc.",
    )
    @app.get("/status/", include_in_schema=False)
    async def get_status(
        session: AsyncSession = Depends(get_db),
        _: str = Depends(validate_clients_audience),
    ) -> ServerStatus:
        """Status route.

        Parameters
        ----------
        session : AsyncSession
            The database session

        Returns
        -------
        ServerStatus
            The status
        """
        active_tasks_count = await TaskService.count_active_tasks(session)
        pending_tasks_count = await TaskService.count_pending_tasks(session)
        return {
            "healthy": True,
            "active_tasks": active_tasks_count,
            "pending_tasks": pending_tasks_count,
            "max_capacity": max_jobs,
            "cpu_count": psutil.cpu_count(logical=False),
            "cpu_percent": psutil.cpu_percent(),
            "total_memory": psutil.virtual_memory().total,
            "used_memory": psutil.virtual_memory().used,
            "memory_percent": psutil.virtual_memory().percent,
        }
