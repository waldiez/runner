# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
#
# flake8: noqa: E501
# pylint: disable=line-too-long

"""Simple waldiez serve sync and async client."""

from ._client import Client as WaldiezServeClient

__all__ = ["WaldiezServeClient"]
