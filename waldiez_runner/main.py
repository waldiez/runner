# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from fastapi_pagination import add_pagination

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
    add_pagination(application)
    add_middlewares(application, settings)
    add_routes(application)
    return application


app = get_app()
