# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught,missing-class-docstring
# pylint: disable=missing-function-docstring,unused-argument
"""Test waldiez_runner.tasks.results_serialization.*."""

from dataclasses import dataclass
from typing import Any

from waldiez_runner.tasks.app.results_serialization import (
    make_serializable_results,
    serialize_dict,
    serialize_list,
)


def test_serialize_dict_basic() -> None:
    """Test serialize_dict function with basic data types."""
    data: dict[str, Any] = {"key1": "value1", "key2": 2, "key3": 3.5}
    result = serialize_dict(data)
    assert result == [{"key1": "value1", "key2": 2, "key3": 3.5}]


def test_serialize_dict_with_nested_dict() -> None:
    """Test serialize_dict function with nested dictionaries."""
    data: dict[str, Any] = {"key1": {"sub_key1": "sub_value1"}, "key2": 2}
    result = serialize_dict(data)
    assert result == [{"key1": {"sub_key1": "sub_value1"}, "key2": 2}]


def test_serialize_dict_with_dataclass() -> None:
    """Test serialize_dict function with dataclass."""

    @dataclass
    class Person:
        name: str
        age: int

    person = Person(name="Alice", age=30)
    data = {"person": person}
    result = serialize_dict(data)
    assert result == [{"person": [{"name": "Alice", "age": 30}]}]


# Test Cases for serialize_list function
def test_serialize_list_basic() -> None:
    """Test serialize_list function with basic data types."""
    data: list[Any] = ["string", 123, 45.67]
    result = serialize_list(data)
    assert result == ["string", 123, 45.67]


def test_serialize_list_with_dicts() -> None:
    """Test serialize_list function with dictionaries."""
    data = [{"key1": "value1"}, {"key2": "value2"}]
    result = serialize_list(data)
    assert result == [{"key1": "value1"}, {"key2": "value2"}]


def test_serialize_list_with_nested_lists() -> None:
    """Test serialize_list function with nested lists."""
    data = [["nested1", "nested2"], ["nested3", "nested4"]]
    result = serialize_list(data)
    assert result == ["nested1", "nested2", "nested3", "nested4"]


def test_serialize_list_with_dataclass() -> None:
    """Test serialize_list function with dataclass."""

    @dataclass
    class Item:
        id: int
        name: str

    items = [Item(1, "Item A"), Item(2, "Item B")]
    data = [items]
    result = serialize_list(data)
    assert result == [{"id": 1, "name": "Item A"}, {"id": 2, "name": "Item B"}]


def test_make_serializable_results_with_dict() -> None:
    """Test serialize_results function with dictionary."""
    data: dict[str, Any] = {"key1": "value1", "key2": 2}
    result = make_serializable_results(data)
    assert result == [{"key1": "value1", "key2": 2}]


def test_make_serializable_results_with_list() -> None:
    """Test serialize_results function with list."""
    data = ["item1", "item2"]
    result = make_serializable_results(data)
    assert result == ["item1", "item2"]


def test_make_serializable_results_with_mixed_types() -> None:
    """Test serialize_results function with mixed data types."""

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
    assert result == [
        {
            "key1": [{"name": "Alice", "age": 30}],
            "key2": 2,
            "key3": ["item1", "item2"],
        }
    ]


def test_make_serializable_results_with_dataclass() -> None:
    """Test serialize_results function with dataclass."""

    @dataclass
    class Person:
        name: str
        age: int

    person = Person(name="Alice", age=30)
    result = make_serializable_results(person)
    assert result == [{"name": "Alice", "age": 30}]


def test_make_serializable_results_with_nested_data() -> None:
    """Test serialize_results function with nested data."""

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
    data = [person]
    result = make_serializable_results(data)
    assert result == [
        {
            "name": "Alice",
            "address": {"street": "123 Main St", "city": "Wonderland"},
        }
    ]
