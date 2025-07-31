# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught,too-many-return-statements
# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Module for serializing results into a JSON-compatible format."""

import json
from dataclasses import asdict, is_dataclass
from typing import Any


def make_serializable_results(data: Any) -> Any:
    """Convert any data structure to JSON-serializable format.

    Parameters
    ----------
    data : Any
        The data to serialize.

    Returns
    -------
    Any
        JSON-serializable version of the data.
    """
    # Handle None
    if data is None:
        return None

    # Handle primitives
    if isinstance(data, (str, int, float, bool)):
        return data

    # Handle dataclasses
    if is_dataclass_instance(data):
        return make_serializable_results(asdict(data))

    # Handle Pydantic models
    if hasattr(data, "model_dump"):
        return data.model_dump(mode="json", fallback=str)

    # Handle dictionaries
    if isinstance(data, dict):
        return {
            str(key): make_serializable_results(value)
            for key, value in data.items()
        }

    # Handle lists, tuples, sets
    if isinstance(data, (list, tuple, set)):
        return [make_serializable_results(item) for item in data]

    # Handle other types by converting to string
    try:
        # Try to JSON serialize first to catch obvious non-serializable types
        json.dumps(data)
        return data
    except (TypeError, ValueError):
        return str(data)


def is_dataclass_instance(obj: Any) -> bool:
    """Check if an object is an instance of a dataclass.

    Parameters
    ----------
    obj : Any
        The object to check.

    Returns
    -------
    bool
        True if the object is a dataclass instance, False otherwise.
    """
    return is_dataclass(obj) and not isinstance(obj, type)
