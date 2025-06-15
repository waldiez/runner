# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pyright: reportUnusedFunction=false,reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false,reportAttributeAccessIssue=false

"""Application entry point."""

import http
import logging
import traceback
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse, Response
from fastapi_pagination import add_pagination
from starlette.exceptions import HTTPException

from waldiez_runner._version import __version__
from waldiez_runner.config import SettingsManager
from waldiez_runner.dependencies import on_shutdown, on_startup
from waldiez_runner.middleware import add_middlewares
from waldiez_runner.routes import add_routes

LOG = logging.getLogger(__name__)


# pylint: disable=unused-argument
@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Application lifespan context manager.

    Parameters
    ----------
    application : FastAPI
        The FastAPI application

    Yields
    ------
    None
        Nothing
    """
    # On startup
    await on_startup()
    yield
    # On shutdown
    await on_shutdown()


def get_app() -> FastAPI:
    """Get the FastAPI application.

    Returns
    -------
    FastAPI
        The FastAPI application
    """
    settings = SettingsManager.load_settings(force_reload=True)
    application = FastAPI(
        lifespan=lifespan,
        docs_url="/docs" if settings.dev else None,
        redoc_url=None,
        title="Waldiez Runner",
        description="Waldiez flows runner.",
        version=__version__,
        openapi_url="/openapi.json",
        default_response_class=ORJSONResponse,
        license_info={
            "name": "Apache 2.0",
            "identifier": "Apache-2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0",
        },
    )

    @application.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException | Exception
    ) -> Response:
        """Custom HTTP exception handler.

        Parameters
        ----------
        request : Request
            The request
        exc : HTTPException | Exception
            The exception

        Returns
        -------
        NResponse
            The response
        """
        LOG.exception(traceback.format_exc())
        status_code = 500
        if hasattr(exc, "status_code"):
            status_code = int(exc.status_code)
        if status_code == 500:  # pragma: no cover
            return ORJSONResponse(
                status_code=status_code,
                content={
                    "detail": "An unexpected error occurred.",
                },
            )
        detail: dict[str, Any] | list[Any] = {
            "detail": http.HTTPStatus(status_code).phrase
        }
        if hasattr(exc, "detail"):
            if isinstance(exc.detail, (dict, list)):
                detail = exc.detail  # pyright: ignore
            elif isinstance(exc.detail, str):  # pragma: no cover
                detail = {"detail": exc.detail}
        return ORJSONResponse(
            content=detail,
            status_code=status_code,
        )

    add_pagination(application)
    add_middlewares(application, settings)
    add_routes(application)
    return application


app = get_app()
