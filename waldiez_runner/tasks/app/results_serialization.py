# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught

"""Module for serializing results into a JSON-compatible format."""

from dataclasses import asdict, is_dataclass
from typing import Any


def serialize_dict(data: dict[Any, Any]) -> list[dict[str, Any]]:
    """Serialize a dictionary into a json-compatible format.

    Parameters
    ----------
    data : dict
        The dictionary to serialize.

    Returns
    -------
    list[dict[str, Any]]
        The serialized dictionary with JSON-compatible types.
    """
    serialized: dict[str, Any] = {}
    for key, value in data.items():
        # If value is a dataclass, recursively serialize it
        if is_dataclass_instance(value):  # Check if it's a dataclass
            serialized[key] = make_serializable_results(
                asdict(value)
            )  # Serialize dataclass object
        elif isinstance(value, dict):  # If it's a nested dict, serialize it
            serialized[key] = serialize_dict(value)[  # pyright: ignore
                0
            ]  # Ensure it’s wrapped in a list
        elif isinstance(value, list):  # If it’s a list, serialize it
            serialized[key] = serialize_list(value)  # pyright: ignore
        else:
            # Primitive types (str, int, float, etc.) are already serializable
            serialized[key] = value
    return [serialized]  # Return as a list


def serialize_list(data: list[Any]) -> list[dict[str, Any]]:
    """Serialize a list into a list of JSON-compatible dictionaries.

    Parameters
    ----------
    data : list
        The list to serialize.

    Returns
    -------
    list[dict[str, Any]]
        The list of serialized items.
    """
    serialized: list[dict[str, Any]] = []
    for item in data:
        if is_dataclass_instance(
            item
        ):  # If the item is a dataclass, serialize it
            serialized.extend(
                make_serializable_results(asdict(item))
            )  # Flatten the result
        elif isinstance(
            item, dict
        ):  # If the item is a dictionary, serialize it
            serialized.append(
                serialize_dict(item)[0]  # pyright: ignore
            )  # Ensure it’s wrapped in a list
        elif isinstance(item, list):  # If the item is a list, serialize it
            # Flatten the result
            serialized.extend(serialize_list(item))  # pyright: ignore
        else:
            # Primitive types (str, int, float, etc.) are already serializable
            serialized.append(item)
    return serialized


def make_serializable_results(results: Any) -> list[dict[str, Any]]:
    """Make the results JSON serializable.

    Parameters
    ----------
    results : Any | list[Any] | dict[Any, Any]
        The results.

    Returns
    -------
    list[dict[str, Any]]
        The json serializable results.
    """
    if isinstance(results, dict):
        return serialize_dict(results)  # pyright: ignore
    if isinstance(results, list):
        return serialize_list(results)  # pyright: ignore
    if is_dataclass_instance(results):
        return serialize_dict(asdict(results))
    return make_serializable_results([results])  # pragma: no cover


def is_dataclass_instance(obj: Any) -> bool:
    """Check if an object is an instance of a dataclass.

    Parameters
    ----------
    obj : Any
        The object.

    Returns
    -------
    bool
        True if the object is an instance of a dataclass, False otherwise.
    """
    return is_dataclass(obj) and not isinstance(obj, type)
