# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Filename extraction and validation utilities."""

import logging
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import HTTPException

LOG = logging.getLogger(__name__)


class FilenameExtractor:
    """Helper class for extracting and validating filenames from URLs."""

    # Characters not allowed in filenames on most filesystems
    INVALID_FILENAME_CHARS = r'[<>:"/\\|?*]'
    MAX_FILENAME_LENGTH = 255

    @staticmethod
    def extract_raw_filename(file_url: str) -> str:
        """Extract the raw filename from URL path.

        Parameters
        ----------
        file_url : str
            The URL to extract filename from.

        Returns
        -------
        str
            Raw filename before sanitization.

        Raises
        ------
        HTTPException
            If URL has no valid path.
        """
        parsed = urlparse(file_url)
        path = parsed.path.rstrip("/")

        if not path or path == "/":
            raise HTTPException(
                status_code=400, detail="Invalid file URL: no path found"
            )

        filename = Path(path).name
        filename = unquote(filename)

        if not filename:
            # Try to use last directory name as fallback
            parts = [p for p in path.split("/") if p]
            filename = parts[-1] if parts else "download"
            filename = unquote(filename)

        return filename

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename by removing invalid characters.

        Parameters
        ----------
        filename : str
            Raw filename to sanitize.

        Returns
        -------
        str
            Sanitized filename.
        """
        # Replace invalid characters with underscores
        sanitized = re.sub(
            FilenameExtractor.INVALID_FILENAME_CHARS, "_", filename
        )

        # Handle edge cases
        if not sanitized or sanitized in (".", ".."):
            sanitized = "download"

        return sanitized

    @staticmethod
    def normalize_extensions(
        extensions: list[str] | tuple[str, ...],
    ) -> list[str]:
        """Normalize extension list to lowercase with leading dots.

        Parameters
        ----------
        extensions : list of str | tuple of str
            Extensions to normalize (with or without dots).

        Returns
        -------
        list of str
            Normalized extensions with dots and lowercase.
        """
        normalized: list[str] = []
        for ext in extensions:
            if not ext.startswith("."):
                ext = "." + ext
            normalized.append(ext.lower())
        return normalized

    @staticmethod
    def validate_extension(
        filename: str, allowed_extensions: list[str], strict_validation: bool
    ) -> None:
        """Validate filename extension against allowed list.

        Parameters
        ----------
        filename : str
            Filename to validate.
        allowed_extensions : list of str
            Normalized allowed extensions.
        strict_validation : bool
            Whether to raise exception or just log warning.

        Raises
        ------
        HTTPException
            If extension is invalid and strict_validation is True.
        """
        current_ext = Path(filename).suffix.lower()
        normalized_str = ", ".join(allowed_extensions)

        if current_ext and current_ext not in allowed_extensions:
            error_msg = (
                f"File extension '{current_ext}' not allowed. "
                f"Allowed: {normalized_str}"
            )
            if strict_validation:
                raise HTTPException(status_code=400, detail=error_msg)
            LOG.warning(error_msg)
        elif not current_ext and strict_validation:
            error_msg = (
                f"File must have an extension. Allowed: {normalized_str}"
            )
            raise HTTPException(status_code=400, detail=error_msg)

    @staticmethod
    def add_default_extension(filename: str, default_extension: str) -> str:
        """Add default extension if filename has no extension.

        Parameters
        ----------
        filename : str
            Filename to potentially modify.
        default_extension : str
            Extension to add (with or without dot).

        Returns
        -------
        str
            Filename with extension added if needed.
        """
        current_ext = Path(filename).suffix

        if not current_ext:
            if not default_extension.startswith("."):
                default_extension = "." + default_extension
            filename += default_extension

        return filename

    @staticmethod
    def truncate_if_too_long(filename: str) -> str:
        """Truncate filename if it exceeds filesystem limits.

        Parameters
        ----------
        filename : str
            Filename to check and potentially truncate.

        Returns
        -------
        str
            Truncated filename if necessary.
        """
        if len(filename) <= FilenameExtractor.MAX_FILENAME_LENGTH:
            return filename

        if "." in filename:
            name, ext = filename.rsplit(".", 1)
            max_name_len = FilenameExtractor.MAX_FILENAME_LENGTH - len(ext) - 1
            filename = name[:max_name_len] + "." + ext
        else:
            filename = filename[: FilenameExtractor.MAX_FILENAME_LENGTH]

        return filename


def get_filename_from_url(
    file_url: str,
    allowed_extensions: list[str] | tuple[str, ...] | None = None,
    default_extension: str | None = None,
    strict_validation: bool = True,
) -> str:
    """Extract filename with flexible extension handling.

    Parameters
    ----------
    file_url : str
        The URL of the file.
    allowed_extensions : list or tuple of str, optional
        List of allowed extensions (with leading dots).
    default_extension : str, optional
        Extension to add if filename has no extension.
        Example: '.pdf' or 'pdf'
    strict_validation : bool, default True
        If True, raises exception for invalid extensions.
        If False, returns filename with warning in logs.

    Returns
    -------
    str
        The validated filename.

    Raises
    ------
    HTTPException
        If the filename is invalid or does not meet the criteria.
    """
    extractor = FilenameExtractor()

    # Extract and sanitize basic filename
    filename = extractor.extract_raw_filename(file_url)
    filename = extractor.sanitize_filename(filename)

    # Handle extension validation and addition
    if allowed_extensions:
        normalized_allowed = extractor.normalize_extensions(allowed_extensions)

        # Add default extension FIRST if no extension and one is provided
        if default_extension and not Path(filename).suffix:
            filename = extractor.add_default_extension(
                filename, default_extension
            )

        # THEN validate the extension (after potentially adding default)
        extractor.validate_extension(
            filename, normalized_allowed, strict_validation
        )

    elif default_extension:
        # No validation list, but add default extension if missing
        filename = extractor.add_default_extension(filename, default_extension)

    # Final truncation check
    filename = extractor.truncate_if_too_long(filename)

    return filename
