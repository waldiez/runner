# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=broad-exception-caught,missing-class-docstring
# pylint: disable=missing-function-docstring,unused-argument
"""Test waldiez_runner.tasks.results_serialization.*."""

from dataclasses import dataclass
from typing import Any

from waldiez_runner.tasks.app.results_serialization import (
    make_serializable_results,
)


def test_make_serializable_results_with_dict_basic() -> None:
    """Test make_serializable_results with basic data types."""
    data: dict[str, Any] = {"key1": "value1", "key2": 2, "key3": 3.5}
    result = make_serializable_results(data)
    assert result == {"key1": "value1", "key2": 2, "key3": 3.5}


def test_make_serializable_results_with_nested_dict() -> None:
    """Test make_serializable_results with nested dictionaries."""
    data: dict[str, Any] = {"key1": {"sub_key1": "sub_value1"}, "key2": 2}
    result = make_serializable_results(data)
    assert result == {"key1": {"sub_key1": "sub_value1"}, "key2": 2}


def test_make_serializable_results_with_dict_containing_dataclass() -> None:
    """Test make_serializable_results with dict containing dataclass."""

    @dataclass
    class Person:
        name: str
        age: int

    person = Person(name="Alice", age=30)
    data = {"person": person}
    result = make_serializable_results(data)
    assert result == {"person": {"name": "Alice", "age": 30}}


def test_make_serializable_results_with_list_basic() -> None:
    """Test make_serializable_results with basic list data types."""
    data: list[Any] = ["string", 123, 45.67]
    result = make_serializable_results(data)
    assert result == ["string", 123, 45.67]


def test_make_serializable_results_with_list_of_dicts() -> None:
    """Test make_serializable_results with list of dictionaries."""
    data = [{"key1": "value1"}, {"key2": "value2"}]
    result = make_serializable_results(data)
    assert result == [{"key1": "value1"}, {"key2": "value2"}]


def test_make_serializable_results_with_nested_lists() -> None:
    """Test make_serializable_results with nested lists."""
    data = [["nested1", "nested2"], ["nested3", "nested4"]]
    result = make_serializable_results(data)
    assert result == [["nested1", "nested2"], ["nested3", "nested4"]]


def test_make_serializable_results_with_list_of_dataclasses() -> None:
    """Test make_serializable_results with list of dataclasses."""

    @dataclass
    class Item:
        id: int
        name: str

    items = [Item(1, "Item A"), Item(2, "Item B")]
    result = make_serializable_results(items)
    assert result == [{"id": 1, "name": "Item A"}, {"id": 2, "name": "Item B"}]


def test_make_serializable_results_with_dict() -> None:
    """Test make_serializable_results with dictionary."""
    data: dict[str, Any] = {"key1": "value1", "key2": 2}
    result = make_serializable_results(data)
    assert result == {"key1": "value1", "key2": 2}


def test_make_serializable_results_with_list() -> None:
    """Test make_serializable_results with list."""
    data = ["item1", "item2"]
    result = make_serializable_results(data)
    assert result == ["item1", "item2"]


def test_make_serializable_results_with_mixed_types() -> None:
    """Test make_serializable_results with mixed data types."""

    @dataclass
    class Person:
        name: str
        age: int

    person = Person(name="Alice", age=30)
    data: dict[str, Any] = {
        "key1": person,
        "key2": 2,
        "key3": ["item1", "item2"],
    }
    result = make_serializable_results(data)
    assert result == {
        "key1": {"name": "Alice", "age": 30},
        "key2": 2,
        "key3": ["item1", "item2"],
    }


def test_make_serializable_results_with_dataclass() -> None:
    """Test make_serializable_results with dataclass."""

    @dataclass
    class Person:
        name: str
        age: int

    person = Person(name="Alice", age=30)
    result = make_serializable_results(person)
    assert result == {"name": "Alice", "age": 30}


def test_make_serializable_results_with_nested_dataclasses() -> None:
    """Test make_serializable_results with nested dataclasses."""

    @dataclass
    class Address:
        street: str
        city: str

    @dataclass
    class Person:
        name: str
        address: Address

    address = Address(street="123 Main St", city="Wonderland")
    person = Person(name="Alice", address=address)
    result = make_serializable_results(person)
    assert result == {
        "name": "Alice",
        "address": {"street": "123 Main St", "city": "Wonderland"},
    }


def test_make_serializable_results_with_sets_and_tuples() -> None:
    """Test make_serializable_results with sets and tuples."""
    data: dict[str, Any] = {
        "set_data": {1, 2, 3},
        "tuple_data": (4, 5, 6),
        "mixed": [{"a": 1}, (7, 8)],
    }
    result = make_serializable_results(data)

    # Sets are converted to lists (order may vary)
    assert set(result["set_data"]) == {1, 2, 3}
    assert result["tuple_data"] == [4, 5, 6]
    assert result["mixed"] == [{"a": 1}, [7, 8]]


def test_make_serializable_results_with_primitives() -> None:
    """Test make_serializable_results with primitive types."""
    assert make_serializable_results("string") == "string"
    assert make_serializable_results(42) == 42
    assert make_serializable_results(3.14) == 3.14
    assert make_serializable_results(True)
    assert not make_serializable_results(None)


def test_make_serializable_results_with_non_json_serializable() -> None:
    """Test make_serializable_results with non-JSON-serializable objects."""

    # pylint: disable=too-few-public-methods
    class CustomObject:
        def __init__(self, value: Any) -> None:
            self.value = value

    obj = CustomObject("test")
    result = make_serializable_results(obj)
    # Should be converted to string representation
    assert isinstance(result, str)
    assert "CustomObject" in result or "test" in result
