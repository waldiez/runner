# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Common utilities for routes."""

from fastapi_pagination import Params
from fastapi_pagination.api import request
from typing_extensions import Literal

Order = Literal["asc", "desc"]
"""Order type for sorting."""


def get_pagination_params() -> Params:
    """Get pagination parameters.

    Returns
    -------
    Params
        The pagination parameters.
    """
    query = request().query_params
    page = 1
    try:
        page = int(query.get("page", "1"))
    except ValueError:  # pragma: no cover
        pass
    size = 50
    try:
        size = int(query.get("size", "50"))
    except ValueError:  # pragma: no cover
        pass
    return Params(page=page, size=size)
