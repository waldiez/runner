# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""Settings manager module."""

from ._common import is_testing
from .settings import Settings


class SettingsManager:
    """Settings manager class."""

    _instance: Settings | None = None

    @classmethod
    def load_settings(
        cls,
        force_reload: bool = False,
    ) -> Settings:
        """Get the settings instance.

        Parameters
        ----------
        force_reload : bool
            Whether to force reload the settings

        Returns
        -------
        Settings
            The settings instance
        """
        if force_reload is True or cls._instance is None:  # pragma: no branch
            instance = Settings.load()
            if force_reload:
                instance.save()
                instance = Settings.load()
            cls._instance = instance
        return cls._instance

    @staticmethod
    def is_testing() -> bool:
        """Check if we are in testing mode.

        Returns
        -------
        bool
            True if we are in testing mode, False otherwise
        Raises
        -------
        RuntimeError
            If the settings instance is not initialized
        """
        return is_testing()

    @classmethod
    def get_settings(cls) -> Settings:
        """Get the settings instance.

        Returns
        -------
        Settings
            The settings instance
        """
        if cls._instance is None:
            return cls.load_settings()
        return cls._instance

    @classmethod
    def reset_settings(cls) -> None:
        """Reset the settings (useful in tests or dynamic reloading)."""
        cls._instance = None
