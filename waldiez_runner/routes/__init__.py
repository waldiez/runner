# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Waldiez runner routes."""

from fastapi import APIRouter, FastAPI, Response

from waldiez_runner.config import SettingsManager

from .auth import router as auth_router
from .other import add_status_route
from .other import router as common_router

# from .stream import stream_router
from .v1 import client_router as v1_client_router
from .v1 import task_router as v1_task_router
from .ws import ws_router


# pylint: disable=unused-argument
def add_routes(app: FastAPI) -> None:
    """Add routes to the FastAPI app.

    Parameters
    ----------
    app : FastAPI
        The FastAPI app
    """
    settings = SettingsManager.load_settings(force_reload=True)
    add_status_route(app, settings.max_jobs)
    api_router = APIRouter(prefix="/api")
    api_router.include_router(v1_task_router, prefix="/v1", tags=["Tasks"])
    api_router.include_router(v1_client_router, prefix="/v1", tags=["Clients"])
    app.include_router(common_router)
    app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
    app.include_router(api_router)
    app.include_router(ws_router)
    # app.include_router(stream_router)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def catch_all(full_path: str = "") -> Response:
        """Catch all requests.

        Parameters
        ----------
        full_path : str
            The full request path

        Returns
        -------
        Response
            The response
        """
        return Response(
            content="",
            status_code=404,
        )


# __all__ = ["add_routes", "stream_router", "common_router", "auth_router"]
__all__ = ["add_routes", "common_router", "auth_router"]
