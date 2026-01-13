# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-return-doc,missing-yield-doc
# pylint: disable=no-self-use
"""Test waldiez_runner.dependencies.storage.utils._filename.*."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from waldiez_runner.dependencies.storage.utils import (
    FilenameExtractor,
    get_filename_from_url,
)

TO_PATCH = "waldiez_runner.dependencies.storage.utils._filename.LOG"


class TestFilenameExtractor:
    """Test cases for FilenameExtractor helper methods."""

    def test_extract_raw_filename_basic(self) -> None:
        """Test basic filename extraction from various URL types."""
        test_cases = [
            ("https://example.com/file.pdf", "file.pdf"),
            ("s3://bucket/folder/document.txt", "document.txt"),
            ("gs://bucket/data.csv", "data.csv"),
            (
                "https://example.com/path/my%20file.docx",
                "my file.docx",
            ),  # URL decoded
        ]

        for url, expected in test_cases:
            result = FilenameExtractor.extract_raw_filename(url)
            assert result == expected, f"Failed for URL: {url}"

    def test_extract_raw_filename_with_query_params(self) -> None:
        """Test filename extraction ignores query parameters."""
        url = "https://example.com/file.pdf?version=1&token=abc123"
        result = FilenameExtractor.extract_raw_filename(url)
        assert result == "file.pdf"

    def test_extract_raw_filename_directory_fallback(self) -> None:
        """Test fallback to directory name when no filename present."""
        test_cases = [
            ("https://example.com/documents/", "documents"),
            ("s3://bucket/folder/subfolder/", "subfolder"),
        ]

        for url, expected in test_cases:
            result = FilenameExtractor.extract_raw_filename(url)
            assert result == expected

    def test_extract_raw_filename_invalid_urls(self) -> None:
        """Test exception handling for invalid URLs."""
        invalid_urls = [
            "https://example.com/",
            "https://example.com",
            "s3://bucket/",
        ]

        for url in invalid_urls:
            with pytest.raises(HTTPException) as exc_info:
                FilenameExtractor.extract_raw_filename(url)
            assert exc_info.value.status_code == 400
            assert "no path found" in exc_info.value.detail

    def test_sanitize_filename(self) -> None:
        """Test filename sanitization."""
        test_cases = [
            ("normal_file.txt", "normal_file.txt"),  # No change
            (
                "file:with<bad>chars.pdf",
                "file_with_bad_chars.pdf",
            ),  # Replace bad chars
            (
                "file/with\\path.txt",
                "file_with_path.txt",
            ),  # Replace path separators
            ("file|with*wild?.doc", "file_with_wild_.doc"),  # Replace wildcards
            ("", "download"),  # Empty filename
            (".", "download"),  # Current directory
            ("..", "download"),  # Parent directory
        ]

        for input_name, expected in test_cases:
            result = FilenameExtractor.sanitize_filename(input_name)
            assert result == expected, f"Failed for input: '{input_name}'"

    def test_normalize_extensions(self) -> None:
        """Test extension normalization."""
        test_cases = [
            (["pdf", "txt"], [".pdf", ".txt"]),  # Add dots
            ([".PDF", ".TXT"], [".pdf", ".txt"]),  # Lowercase
            (
                ["pdf", ".docx", "CSV"],
                [".pdf", ".docx", ".csv"],
            ),  # Mixed formats
        ]

        for input_exts, expected in test_cases:
            result = FilenameExtractor.normalize_extensions(input_exts)
            assert result == expected

    def test_validate_extension_valid(self) -> None:
        """Test extension validation with valid extensions."""
        # Should not raise exception
        FilenameExtractor.validate_extension(
            "document.pdf", [".pdf", ".txt"], strict_validation=True
        )

        # Case insensitive
        FilenameExtractor.validate_extension(
            "document.PDF", [".pdf"], strict_validation=True
        )

    def test_validate_extension_invalid_strict(self) -> None:
        """Test extension validation with invalid extensions in strict mode."""
        with pytest.raises(HTTPException) as exc_info:
            FilenameExtractor.validate_extension(
                "document.xyz", [".pdf", ".txt"], strict_validation=True
            )
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail

    def test_validate_extension_invalid_non_strict(self) -> None:
        """Test ext validation with invalid extensions in non-strict mode."""
        with patch(f"{TO_PATCH}.warning") as mock_warning:
            FilenameExtractor.validate_extension(
                "document.xyz", [".pdf", ".txt"], strict_validation=False
            )
            mock_warning.assert_called_once()

    def test_validate_extension_missing_strict(self) -> None:
        """Test validation with missing extension in strict mode."""
        with pytest.raises(HTTPException) as exc_info:
            FilenameExtractor.validate_extension(
                "document", [".pdf", ".txt"], strict_validation=True
            )
        assert exc_info.value.status_code == 400
        assert "must have an extension" in exc_info.value.detail

    def test_add_default_extension(self) -> None:
        """Test adding default extension."""
        test_cases = [
            ("document", "pdf", "document.pdf"),  # Add extension
            ("document", ".pdf", "document.pdf"),  # Add extension with dot
            ("document.txt", "pdf", "document.txt"),  # Don't change existing
        ]

        for filename, default_ext, expected in test_cases:
            result = FilenameExtractor.add_default_extension(
                filename, default_ext
            )
            assert result == expected

    def test_truncate_if_too_long(self) -> None:
        """Test filename truncation."""
        # Normal length filename
        normal_name = "document.pdf"
        result = FilenameExtractor.truncate_if_too_long(normal_name)
        assert result == normal_name

        # Very long filename with extension
        long_name = "a" * 300 + ".pdf"
        result = FilenameExtractor.truncate_if_too_long(long_name)
        assert len(result) == 255
        assert result.endswith(".pdf")

        # Very long filename without extension
        long_name_no_ext = "b" * 300
        result = FilenameExtractor.truncate_if_too_long(long_name_no_ext)
        assert len(result) == 255


class TestGetFilenameFromUrl:
    """Test cases for the main get_filename_from_url function."""

    def test_basic_functionality(self) -> None:
        """Test basic filename extraction without validation."""
        test_cases = [
            ("https://example.com/document.pdf", "document.pdf"),
            ("s3://bucket/folder/data.csv", "data.csv"),
            ("gs://storage/image.jpg", "image.jpg"),
        ]

        for url, expected in test_cases:
            result = get_filename_from_url(url)
            assert result == expected

    def test_with_allowed_extensions_valid(self) -> None:
        """Test with valid allowed extensions."""
        url = "https://example.com/document.pdf"
        result = get_filename_from_url(url, allowed_extensions=["pdf", "txt"])
        assert result == "document.pdf"

        # Test case insensitive
        url2 = "https://example.com/document.PDF"
        result2 = get_filename_from_url(url2, allowed_extensions=[".pdf"])
        assert result2 == "document.PDF"

    def test_with_allowed_extensions_invalid_strict(self) -> None:
        """Test with invalid extensions in strict mode."""
        url = "https://example.com/document.xyz"
        with pytest.raises(HTTPException) as exc_info:
            get_filename_from_url(url, allowed_extensions=["pdf", "txt"])
        assert exc_info.value.status_code == 400

    def test_with_allowed_extensions_invalid_non_strict(self) -> None:
        """Test with invalid extensions in non-strict mode."""
        url = "https://example.com/document.xyz"
        with patch(f"{TO_PATCH}.warning"):
            result = get_filename_from_url(
                url, allowed_extensions=["pdf", "txt"], strict_validation=False
            )
            assert result == "document.xyz"

    def test_with_default_extension_no_current_extension(self) -> None:
        """Test adding default extension when filename has none."""
        url = "https://example.com/document"
        result = get_filename_from_url(url, default_extension="pdf")
        assert result == "document.pdf"

        # Test with dot
        result2 = get_filename_from_url(url, default_extension=".txt")
        assert result2 == "document.txt"

    def test_with_default_extension_has_current_extension(self) -> None:
        """Test that default extension is not added when one exists."""
        url = "https://example.com/document.csv"
        result = get_filename_from_url(url, default_extension="pdf")
        assert result == "document.csv"

    def test_combined_validation_and_default(self) -> None:
        """Test combination of allowed extensions and default extension."""
        # URL without extension, should add default
        url = "https://example.com/document"
        result = get_filename_from_url(
            url, allowed_extensions=["pdf", "txt"], default_extension="pdf"
        )
        assert result == "document.pdf"

    def test_missing_extension_with_allowed_strict(self) -> None:
        """Test missing extension with allowed extensions in strict mode."""
        url = "https://example.com/document"
        with pytest.raises(HTTPException) as exc_info:
            get_filename_from_url(url, allowed_extensions=["pdf", "txt"])
        assert "must have an extension" in exc_info.value.detail

    def test_url_encoding_and_sanitization(self) -> None:
        """Test URL decoding and character sanitization."""
        url = "https://example.com/my%20file%3Awith%3Cbad%3Echars.pdf"
        result = get_filename_from_url(url)
        assert result == "my file_with_bad_chars.pdf"

    def test_edge_cases(self) -> None:
        """Test various edge cases."""
        # Empty path fallback
        with pytest.raises(HTTPException):
            get_filename_from_url("https://example.com/")

        # Directory as filename
        result = get_filename_from_url("https://example.com/folder/")
        assert result == "folder"

    def test_long_filename_truncation(self) -> None:
        """Test that very long filenames are truncated."""
        long_filename = "a" * 300
        url = f"https://example.com/{long_filename}.pdf"
        result = get_filename_from_url(url)
        assert len(result) == 255
        assert result.endswith(".pdf")

    def test_different_url_schemes(self) -> None:
        """Test different URL schemes work correctly."""
        schemes_and_urls = [
            ("https://example.com/file.pdf", "file.pdf"),
            ("http://example.com/file.pdf", "file.pdf"),
            ("s3://bucket/path/file.pdf", "file.pdf"),
            ("gs://bucket/file.pdf", "file.pdf"),
            ("file:///local/path/file.pdf", "file.pdf"),
            ("ftp://server.com/file.pdf", "file.pdf"),
        ]

        for url, expected in schemes_and_urls:
            result = get_filename_from_url(url)
            assert result == expected, f"Failed for scheme in URL: {url}"


# Pytest fixtures and parameterized tests
@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com/document.pdf", "document.pdf"),
        ("s3://my-bucket/folder/data.csv", "data.csv"),
        ("gs://storage/images/photo.jpg", "photo.jpg"),
        ("https://example.com/my%20file.txt", "my file.txt"),
    ],
)
def test_basic_extraction_parametrized(url: str, expected: str) -> None:
    """Parametrized test for basic filename extraction."""
    result = get_filename_from_url(url)
    assert result == expected


@pytest.mark.parametrize(
    "filename,extensions,should_raise",
    [
        ("document.pdf", ["pdf", "txt"], False),
        ("document.PDF", [".pdf"], False),  # Case insensitive
        ("document.xyz", ["pdf", "txt"], True),
        ("document", ["pdf"], True),  # Missing extension
    ],
)
def test_extension_validation_parametrized(
    filename: str,
    extensions: list[str],
    should_raise: bool,
) -> None:
    """Parametrized test for extension validation."""
    url = f"https://example.com/{filename}"

    if should_raise:
        with pytest.raises(HTTPException):
            get_filename_from_url(url, allowed_extensions=extensions)
    else:
        result = get_filename_from_url(url, allowed_extensions=extensions)
        assert result == filename
