# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught,too-many-return-statements
# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
# pyright: reportMissingTypeStubs=false
"""Module for serializing results into a JSON-compatible format."""

import json
import traceback
from dataclasses import asdict, is_dataclass
from typing import Any

from autogen.io.run_response import RunResponse  # type: ignore


def make_serializable_results(data: Any) -> Any:  # noqa: C901
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
    if isinstance(data, RunResponse):
        return serialize_run_response(data)
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
    except BaseException:
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


def serialize_run_response(
    data: RunResponse,
) -> dict[str, Any]:
    """Serialize a RunResponse object to a dictionary.

    Parameters
    ----------
    data : RunResponse
        The RunResponse object to serialize.

    Returns
    -------
    dict[str, Any]
        The serialized RunResponse as a dictionary.
    """
    try:
        results_dict = {
            "uuid": str(data.uuid),
            "messages": list(data.messages),
            "agents": list(data.agents),
            "cost": (
                data.cost.model_dump_json(serialize_as_any=True, fallback=str)
                if data.cost
                else None
            ),
            "summary": data.summary,
            "context_variables": (
                data.context_variables.model_dump_json(
                    serialize_as_any=True, fallback=str
                )
                if data.context_variables
                else None
            ),
            "last_speaker": data.last_speaker,
        }
        return results_dict
    except Exception as e:
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
