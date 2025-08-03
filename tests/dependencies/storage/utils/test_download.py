# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-return-doc,missing-yield-doc
# pylint: disable=no-self-use,unused-argument,too-many-locals
"""Test waldiez_runner.dependencies.storage.utils._download.*."""

import hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import (  # type: ignore[import-untyped]
    ClientError,
    NoCredentialsError,
)
from fastapi import HTTPException

# from google.cloud.exceptions import NotFound
from waldiez_runner.dependencies.storage.utils import (  # download_gcs_file,
    download_file,
    download_ftp_file,
    download_http_file,
    download_s3_file,
    download_sftp_file,
)
from waldiez_runner.dependencies.storage.utils._download import (
    _validate_file_content,  # pyright: ignore[reportPrivateUsage]
)


class TestValidateFileContent:
    """Test the _validate_file_content helper function."""

    @pytest.mark.anyio
    async def test_validate_file_content_success(self) -> None:
        """Test successful file content validation."""
        chunk = b'{"test": "data"}'

        with patch("puremagic.from_string", return_value="application/json"):
            # Should not raise an exception
            await _validate_file_content(chunk, 100, 1000)

    @pytest.mark.anyio
    async def test_validate_file_content_too_large(self) -> None:
        """Test validation with file too large."""
        chunk = b'{"test": "data"}'

        with pytest.raises(HTTPException) as exc_info:
            await _validate_file_content(chunk, 2000, 1000)

        assert exc_info.value.status_code == 400
        assert "exceeds maximum size" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_validate_file_content_empty(self) -> None:
        """Test validation with empty chunk."""
        chunk = b""

        with pytest.raises(HTTPException) as exc_info:
            await _validate_file_content(chunk, 0, 1000)

        assert exc_info.value.status_code == 400
        assert "Downloaded file is empty" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_validate_file_content_no_mime(self) -> None:
        """Test validation when MIME type cannot be detected."""
        chunk = b"some random data"

        with patch("puremagic.from_string", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await _validate_file_content(chunk, 100, 1000)

            assert exc_info.value.status_code == 400
            assert "Could not detect MIME type" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_validate_file_content_invalid_mime(self) -> None:
        """Test validation with invalid MIME type."""
        chunk = b"some data"

        with patch(
            "puremagic.from_string", return_value="application/x-executable"
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _validate_file_content(chunk, 100, 1000)

            assert exc_info.value.status_code == 400
            assert "Invalid file type" in exc_info.value.detail


class TestDownloadS3File:
    """Test S3 file download functionality."""

    @pytest.mark.anyio
    async def test_download_s3_file_success(self) -> None:
        """Test successful S3 file download."""
        mock_s3_client = MagicMock()
        mock_s3_client.head_object.return_value = {"ContentLength": 100}

        mock_body = MagicMock()
        mock_body.read.side_effect = [b'{"test": "data"}', b""]  # Data then EOF
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        with patch("boto3.client", return_value=mock_s3_client):
            with patch(
                "puremagic.from_string", return_value="application/json"
            ):
                with patch("aiofiles.tempfile.NamedTemporaryFile") as mock_temp:
                    mock_temp.return_value.__aenter__ = AsyncMock(
                        return_value=Path("test_file")
                    )
                    mock_temp.return_value.__aexit__ = AsyncMock()
                    mock_temp.return_value.name = "test_file"

                    with patch("aiofiles.open") as mock_aiofiles_open:
                        mock_file = AsyncMock()
                        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(
                            return_value=mock_file
                        )
                        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(
                            return_value=None
                        )

                        hash_val, temp_path = await download_s3_file(
                            "s3://test-bucket/test.json"
                        )

                        assert len(hash_val) == 32
                        assert temp_path == "test_file"

    @pytest.mark.anyio
    async def test_download_s3_file_invalid_url(self) -> None:
        """Test S3 download with invalid URL format."""
        with pytest.raises(HTTPException) as exc_info:
            await download_s3_file("s3://")

        assert exc_info.value.status_code == 400
        assert "Invalid S3 URL format" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_download_s3_file_not_found(self, tmp_path: Path) -> None:
        """Test S3 download with object not found."""

        mock_s3_client = MagicMock()
        error_response = {
            "Error": {"Code": "NoSuchKey", "Message": "Not found"}
        }
        mock_s3_client.head_object.side_effect = ClientError(
            error_response, "HeadObject"
        )

        with patch("boto3.client", return_value=mock_s3_client):
            with patch("aiofiles.tempfile.NamedTemporaryFile") as mock_temp:
                mock_temp.return_value.__aenter__ = AsyncMock(
                    return_value=tmp_path / "test_file"
                )
                mock_temp.return_value.__aexit__ = AsyncMock()
                mock_temp.return_value.name = "test_file"

                with pytest.raises(HTTPException) as exc_info:
                    await download_s3_file("s3://test-bucket/missing.json")

                assert exc_info.value.status_code == 404
                assert "S3 object not found" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_download_s3_file_no_credentials(
        self, tmp_path: Path
    ) -> None:
        """Test S3 download with no credentials."""

        with patch("boto3.client", side_effect=NoCredentialsError()):
            with patch("aiofiles.tempfile.NamedTemporaryFile") as mock_temp:
                mock_temp.return_value.__aenter__ = AsyncMock(
                    return_value=tmp_path / "test_file"
                )
                mock_temp.return_value.__aexit__ = AsyncMock()
                mock_temp.return_value.name = "test_file"

                with pytest.raises(HTTPException) as exc_info:
                    await download_s3_file("s3://test-bucket/test.json")

                assert exc_info.value.status_code == 401
                assert "AWS credentials not found" in exc_info.value.detail


# class TestDownloadGcsFile:
#     """Test GCS file download functionality."""

#     @pytest.mark.anyio
#     async def test_download_gcs_file_success(self) -> None:
#         """Test successful GCS file download."""
#         mock_blob = MagicMock()
#         mock_blob.size = 100
#         mock_blob.reload.return_value = None
#         mock_blob.download_as_bytes.return_value = b'{"test": "data"}'

#         mock_bucket = MagicMock()
#         mock_bucket.blob.return_value = mock_blob

#         mock_client = MagicMock()
#         mock_client.bucket.return_value = mock_bucket

#         with patch(
#             "waldiez_runner.dependencies.storage.utils._download.Client",
#             return_value=mock_client,
#         ):
#             with patch(
#                 "puremagic.from_string", return_value="application/json"
#             ):
#            with patch("aiofiles.tempfile.NamedTemporaryFile") as mock_temp:
#                     mock_temp.return_value.__aenter__ = AsyncMock(
#                         return_value=Path("test_file")
#                     )
#                     mock_temp.return_value.__aexit__ = AsyncMock()
#                     mock_temp.return_value.name = "test_file"

#                     with patch("aiofiles.open") as mock_aiofiles_open:
#                         mock_file = AsyncMock()
#                     mock_aiofiles_open.return_value.__aenter__ = AsyncMock(
#                             return_value=mock_file
#                         )
#                         mock_aiofiles_open.return_value.__aexit__ = AsyncMock(
#                             return_value=None
#                         )

#                         hash_val, temp_path = await download_gcs_file(
#                             "gs://test-bucket/test.json"
#                         )

#                         assert len(hash_val) == 32
#                         assert temp_path == "test_file"

#     @pytest.mark.anyio
#     async def test_download_gcs_file_invalid_url(self) -> None:
#         """Test GCS download with invalid URL format."""
#         with pytest.raises(HTTPException) as exc_info:
#             await download_gcs_file("gs://")

#         assert exc_info.value.status_code == 400
#         assert "Invalid GCS URL format" in exc_info.value.detail

#     @pytest.mark.anyio
#     async def test_download_gcs_file_not_found(self) -> None:
#         """Test GCS download with object not found."""

#         mock_blob = MagicMock()
#         mock_blob.size = 100
#         mock_blob.reload.side_effect = NotFound(  # type: ignore
#             "Object not found",
#         )

#         mock_bucket = MagicMock()
#         mock_bucket.blob.return_value = mock_blob

#         mock_client = MagicMock()
#         mock_client.bucket.return_value = mock_bucket

#         with patch(
#             "waldiez_runner.dependencies.storage.utils._download.Client",
#             return_value=mock_client,
#         ):
#             with patch("aiofiles.tempfile.NamedTemporaryFile") as mock_temp:
#                 mock_temp.return_value.__aenter__ = AsyncMock(
#                     return_value=Path("test_file")
#                 )
#                 mock_temp.return_value.__aexit__ = AsyncMock()
#                 mock_temp.return_value.name = "test_file"

#                 with pytest.raises(HTTPException) as exc_info:
#                     await download_gcs_file("gs://test-bucket/missing.json")

#                 assert exc_info.value.status_code == 404
#                 assert "GCS object not found" in exc_info.value.detail


class TestDownloadFile:
    """Test local file download functionality."""

    @pytest.mark.anyio
    async def test_download_file_success(self, tmp_path: Path) -> None:
        """Test successful local file download."""
        # Create a test file
        test_file = tmp_path / "test_download_file_success.json"
        test_content = b'{"test": "data"}'
        test_file.write_bytes(test_content)

        file_url = f"file://{test_file}"

        with patch("puremagic.from_string", return_value="application/json"):
            with patch("aiofiles.tempfile.NamedTemporaryFile") as mock_temp:
                mock_temp.return_value.__aenter__ = AsyncMock(
                    return_value=Path("test_file")
                )
                mock_temp.return_value.__aexit__ = AsyncMock()
                mock_temp.return_value.name = "test_file"

                # Mock aiofiles operations
                with patch("aiofiles.os.path.exists", return_value=True):
                    with patch("aiofiles.os.path.isfile", return_value=True):
                        with patch("aiofiles.os.stat") as mock_stat:
                            mock_stat_result = MagicMock()
                            mock_stat_result.st_size = len(test_content)
                            mock_stat.return_value = mock_stat_result

                            with patch("aiofiles.open") as mock_aiofiles_open:
                                # Mock source file
                                mock_src_file = AsyncMock()
                                mock_src_file.read.side_effect = [
                                    test_content,
                                    b"",
                                ]

                                # Mock destination file
                                mock_dst_file = AsyncMock()

                                mock_aiofiles_open.side_effect = [
                                    AsyncMock(
                                        __aenter__=AsyncMock(
                                            return_value=mock_src_file
                                        )
                                    ),
                                    AsyncMock(
                                        __aenter__=AsyncMock(
                                            return_value=mock_dst_file
                                        )
                                    ),
                                ]

                                hash_val, temp_path = await download_file(
                                    file_url
                                )

                                assert len(hash_val) == 32
                                assert temp_path == "test_file"

    @pytest.mark.anyio
    async def test_download_file_invalid_url(self) -> None:
        """Test file download with invalid URL (relative path)."""
        with pytest.raises(HTTPException) as exc_info:
            await download_file("file://relative/path")

        assert exc_info.value.status_code == 404
        assert "Source file not found" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_download_file_not_found(self) -> None:
        """Test file download with non-existent file."""
        with patch("aiofiles.tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp.return_value.__aenter__ = AsyncMock(
                return_value=Path("test_file")
            )
            mock_temp.return_value.__aexit__ = AsyncMock()
            mock_temp.return_value.name = "test_file"

            with patch("aiofiles.os.path.exists", return_value=False):
                with pytest.raises(HTTPException) as exc_info:
                    await download_file("file:///nonexistent/file.json")

                assert exc_info.value.status_code == 404
                assert "Source file not found" in exc_info.value.detail


class TestDownloadHttpFile:
    """Test HTTP file download functionality."""

    @pytest.mark.anyio
    async def test_download_http_file_success(self, tmp_path: Path) -> None:
        """Test successful HTTP file download."""
        test_content = b'{"mock": "data"}'

        # Patch puremagic MIME detection
        with patch("puremagic.from_string", return_value="application/json"):
            # Patch aiofiles.tempfile.NamedTemporaryFile
            with patch("aiofiles.tempfile.NamedTemporaryFile") as mock_tempfile:
                mock_temp_path = tmp_path / "mock_download_file"
                mock_tempfile.return_value.__aenter__.return_value = (
                    mock_temp_path
                )
                mock_tempfile.return_value.__aexit__.return_value = None
                mock_tempfile.return_value.name = str(mock_temp_path)

                # Patch aiofiles.open
                mock_file = AsyncMock()
                with patch(
                    "aiofiles.open",
                    return_value=AsyncMock(
                        __aenter__=AsyncMock(return_value=mock_file),
                        __aexit__=AsyncMock(),
                    ),
                ):
                    # Mock aiohttp content stream
                    mock_content = AsyncMock()

                    async def mock_iter_chunked(
                        chunk_size: int,
                    ) -> AsyncGenerator[bytes, None]:
                        """Mock content iterator."""
                        yield test_content

                    mock_content.iter_chunked = mock_iter_chunked

                    # Mock response object
                    mock_response = MagicMock()
                    mock_response.status = 200
                    mock_response.headers = {
                        "Content-Length": str(len(test_content))
                    }
                    mock_response.content = mock_content

                    # Patch aiohttp.ClientSession context
                    mock_get_cm = AsyncMock()
                    mock_get_cm.__aenter__.return_value = mock_response
                    mock_get_cm.__aexit__.return_value = None

                    mock_session = MagicMock()
                    mock_session.get.return_value = mock_get_cm

                    mock_session_cm = AsyncMock()
                    mock_session_cm.__aenter__.return_value = mock_session
                    mock_session_cm.__aexit__.return_value = None

                    with patch(
                        "aiohttp.ClientSession", return_value=mock_session_cm
                    ):
                        hash_val, path = await download_http_file(
                            "http://example.com/file.json"
                        )
                        assert isinstance(hash_val, str)
                        assert path == str(mock_temp_path.name)

    @pytest.mark.anyio
    async def test_download_http_file_non_200_status(
        self, tmp_path: Path
    ) -> None:
        """Test HTTP file download with non-200 response."""
        with patch("aiofiles.tempfile.NamedTemporaryFile") as mock_tempfile:
            mock_temp_path = tmp_path / "mock_http_error"
            mock_tempfile.return_value.__aenter__.return_value = mock_temp_path
            mock_tempfile.return_value.__aexit__.return_value = None
            mock_tempfile.return_value.name = str(mock_temp_path)

            mock_response = MagicMock()
            mock_response.status = 404
            mock_response.headers = {}
            mock_response.content = AsyncMock()

            mock_get_cm = AsyncMock()
            mock_get_cm.__aenter__.return_value = mock_response
            mock_get_cm.__aexit__.return_value = None

            mock_session = MagicMock()
            mock_session.get.return_value = mock_get_cm

            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__.return_value = mock_session
            mock_session_cm.__aexit__.return_value = None

            with patch("aiohttp.ClientSession", return_value=mock_session_cm):
                with pytest.raises(HTTPException) as exc_info:
                    await download_http_file("http://example.com/missing")
                assert exc_info.value.status_code == 400
                assert "HTTP 404" in exc_info.value.detail


class TestDownloadSftpFile:
    """Test SFTP file download functionality."""

    @pytest.mark.anyio
    async def test_download_sftp_file_success(self, tmp_path: Path) -> None:
        """Test successful SFTP file download."""
        test_content = b'{"mock": "data"}'
        temp_path = tmp_path / "mock_sftp_file"

        mock_file = MagicMock()
        mock_file.read = AsyncMock(side_effect=[test_content, b""])

        mock_stat_result = MagicMock()
        mock_stat_result.size = len(test_content)

        mock_sftp = MagicMock()
        mock_sftp.stat = AsyncMock(return_value=mock_stat_result)

        @asynccontextmanager
        async def fake_open(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[MagicMock]:
            """Fake open method to simulate SFTP file."""
            yield mock_file

        mock_sftp.open = fake_open

        @asynccontextmanager
        async def fake_start_sftp_client(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[MagicMock]:
            """Fake start_sftp_client to return mock SFTP client."""
            yield mock_sftp

        mock_conn = MagicMock()
        mock_conn.start_sftp_client = fake_start_sftp_client

        @asynccontextmanager
        async def fake_connect(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[MagicMock]:
            """Fake asyncssh.connect to return mock connection."""
            yield mock_conn

        with patch("asyncssh.connect", new=fake_connect):
            with patch("aiofiles.tempfile.NamedTemporaryFile") as mock_temp:
                mock_temp.return_value.__aenter__.return_value = temp_path
                mock_temp.return_value.__aexit__.return_value = None
                mock_temp.return_value.name = str(temp_path)

                mock_dst = AsyncMock()

                @asynccontextmanager
                async def fake_open_dst(
                    path: str, mode: str
                ) -> AsyncIterator[MagicMock]:
                    """Fake open method for destination file."""
                    yield mock_dst

                with patch("aiofiles.open", new=fake_open_dst):
                    with patch(
                        "puremagic.from_string", return_value="application/json"
                    ):
                        hash_val, result_path = await download_sftp_file(
                            "sftp://user:pass@host/file.txt"
                        )

                        expected_hash = hashlib.md5(
                            test_content, usedforsecurity=False
                        ).hexdigest()
                        assert hash_val == expected_hash
                        assert result_path == str(temp_path.name)

    @pytest.mark.anyio
    async def test_download_sftp_file_invalid_url(self) -> None:
        """Test SFTP download with invalid URL."""
        with pytest.raises(HTTPException) as exc_info:
            await download_sftp_file("sftp://")

        assert exc_info.value.status_code == 400
        assert "Invalid SFTP URL format" in exc_info.value.detail


# pylint: disable=too-few-public-methods
class TestDownloadFtpFile:
    """Test FTP file download functionality."""

    @pytest.mark.anyio
    async def test_download_ftp_file_invalid_url(self) -> None:
        """Test FTP download with invalid URL."""
        with pytest.raises(HTTPException) as exc_info:
            await download_ftp_file("ftp://")

        assert exc_info.value.status_code == 400
        assert "Invalid FTP URL format" in exc_info.value.detail
