# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""External token service."""

# pylint: disable=unused-import,too-few-public-methods

from ._external_token_service import (
    ExternalTokenResponse,
    get_user_info,
    verify_external_token,
)


class ExternalTokenService:
    """External token service."""

    get_user_info = staticmethod(get_user_info)
    verify_external_token = staticmethod(verify_external_token)


__all__ = ["ExternalTokenService", "ExternalTokenResponse"]
