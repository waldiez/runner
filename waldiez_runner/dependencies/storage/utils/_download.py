# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pyright: reportUnknownMemberType=false,reportUnknownVariableType=false
# pyright: reportMissingTypeStubs=false,reportUnknownArgumentType=false
# pylint: disable=too-complex,too-many-locals,unused-argument
# pylint: disable=too-many-try-statements,too-many-statements,too-many-branches
# flake8: noqa: C901

"""Download utilities for storage services."""

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiofiles
import aiofiles.tempfile
import aioftp
import aiohttp
import asyncssh
import boto3  # type: ignore[import-untyped]
import puremagic
from aiofiles import os
from botocore.exceptions import (  # type: ignore[import-untyped]
    ClientError,
    NoCredentialsError,
)
from fastapi import HTTPException

from ._common import ALLOWED_MIME_TYPES, CHUNK_SIZE, MAX_FILE_SIZE

LOG = logging.getLogger(__name__)


async def _validate_file_content(
    chunk: bytes, file_size: int, max_size: int
) -> None:
    """Validate file content (MIME type and size).

    Parameters
    ----------
    chunk : bytes
        First chunk of file data.
    file_size : int
        Current file size.
    max_size : int
        Maximum allowed file size.

    Raises
    ------
    HTTPException
        If validation fails.
    """
    if file_size > max_size:
        max_size_mb = f"{max_size / 1024 / 1024:.1f}"
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size of {max_size_mb} MB",
        )

    if not chunk:
        raise HTTPException(status_code=400, detail="Downloaded file is empty")

    detected_mime = puremagic.from_string(chunk, mime=True)
    if not detected_mime:
        raise HTTPException(
            status_code=400, detail="Could not detect MIME type"
        )

    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400, detail=f"Invalid file type: {detected_mime}"
        )


async def download_http_file(
    file_url: str,
    max_size: int | None = None,
) -> tuple[str, str]:
    """Download file from HTTP/HTTPS URL.

    Parameters
    ----------
    file_url : str
        HTTP/HTTPS URL to download from.
    max_size : int, optional
        Maximum file size in bytes.

    Returns
    -------
    tuple[str, str]
        MD5 hash and temporary file path.

    Raises
    ------
    HTTPException
        If download fails or file is invalid.
    """

    if max_size is None:
        max_size = MAX_FILE_SIZE

    file_size = 0
    hash_md5 = hashlib.md5(usedforsecurity=False)

    # Create temporary file
    async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = Path(str(temp_file.name))
    try:
        timeout = aiohttp.ClientTimeout(total=300, connect=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(file_url) as response:
                if response.status != 200:
                    msg = f"Failed to download file: HTTP {response.status}"
                    raise HTTPException(status_code=400, detail=msg)

                # Check Content-Length if available
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > max_size:
                    max_size_mb = f"{max_size / 1024 / 1024:.1f}"
                    raise HTTPException(
                        status_code=400,
                        detail=f"File exceeds maximum size of {max_size_mb} MB",
                    )

                first_chunk = True
                async with aiofiles.open(temp_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(
                        CHUNK_SIZE
                    ):
                        if not chunk:
                            continue

                        file_size += len(chunk)

                        # Validate first chunk
                        if first_chunk:
                            await _validate_file_content(
                                chunk, file_size, max_size
                            )
                            first_chunk = False
                        elif file_size > max_size:
                            max_size_mb = f"{max_size / 1024 / 1024:.1f}"
                            msg = (
                                f"File exceeds maximum size of {max_size_mb} MB"
                            )
                            raise HTTPException(status_code=400, detail=msg)

                        hash_md5.update(chunk)
                        await f.write(chunk)

        if file_size == 0:
            raise HTTPException(
                status_code=400, detail="Downloaded file is empty"
            )

        LOG.info("Downloaded HTTP file: %s (%d bytes)", file_url, file_size)
        return hash_md5.hexdigest(), str(temp_path)

    except HTTPException:
        temp_path.unlink(missing_ok=True)
        raise
    except Exception as error:
        temp_path.unlink(missing_ok=True)
        LOG.error("Failed to download HTTP file %s: %s", file_url, error)
        raise HTTPException(
            status_code=500, detail=f"Failed to download file: {str(error)}"
        ) from error


async def download_s3_file(
    file_url: str,
    max_size: int | None = None,
) -> tuple[str, str]:
    """Download file from S3 URL.

    Parameters
    ----------
    file_url : str
        S3 URL (s3://bucket/key).
    max_size : int | None, optional
        Maximum file size in bytes.

    Returns
    -------
    tuple[str, str]
        MD5 hash and temporary file path.

    Raises
    ------
    HTTPException
        If download fails or file is invalid.
    """
    if max_size is None:
        max_size = MAX_FILE_SIZE

    # Parse S3 URL: s3://bucket/key
    parsed = urlparse(file_url)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    if not bucket or not key:
        raise HTTPException(
            status_code=400,
            detail="Invalid S3 URL format. Expected: s3://bucket/key",
        )

    file_size = 0
    hash_md5 = hashlib.md5(usedforsecurity=False)

    # Create temporary file
    async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = Path(str(temp_file.name))

    try:
        # Run boto3 operations in thread pool to avoid blocking
        loop = asyncio.get_event_loop()

        def _check_s3_object() -> int:
            """Check S3 object size."""
            s3_client = boto3.client("s3")
            head_response = s3_client.head_object(Bucket=bucket, Key=key)
            return head_response.get("ContentLength", 0)

        def _get_s3_object() -> dict[str, Any]:
            """Get S3 object."""
            s3_client = boto3.client("s3")
            return s3_client.get_object(Bucket=bucket, Key=key)

        # Check object size first
        try:
            content_length = await loop.run_in_executor(None, _check_s3_object)
            if content_length > max_size:
                max_size_mb = f"{max_size / 1024 / 1024:.1f}"
                raise HTTPException(
                    status_code=400,
                    detail=f"File exceeds maximum size of {max_size_mb} MB",
                )
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise HTTPException(
                    status_code=404, detail="S3 object not found"
                ) from e
            error_message = e.response["Error"].get("Message", "Unknown error")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to access S3 object: {error_message}",
            ) from e

        # Download object
        response = await loop.run_in_executor(None, _get_s3_object)

        first_chunk = True
        async with aiofiles.open(temp_path, "wb") as f:
            # Read in chunks using thread pool
            while True:
                chunk = await loop.run_in_executor(
                    None, response["Body"].read, CHUNK_SIZE
                )
                if not chunk:
                    break

                file_size += len(chunk)

                # Validate first chunk
                if first_chunk:
                    await _validate_file_content(chunk, file_size, max_size)
                    first_chunk = False
                elif file_size > max_size:
                    max_size_mb = f"{max_size / 1024 / 1024:.1f}"
                    raise HTTPException(
                        status_code=400,
                        detail=f"File exceeds maximum size of {max_size_mb} MB",
                    )

                hash_md5.update(chunk)
                await f.write(chunk)

        if file_size == 0:
            raise HTTPException(
                status_code=400, detail="Downloaded file is empty"
            )

        LOG.info("Downloaded S3 file: %s (%d bytes)", file_url, file_size)
        return hash_md5.hexdigest(), str(temp_path)

    except HTTPException:
        temp_path.unlink(missing_ok=True)
        raise
    except NoCredentialsError as e:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=401,
            detail="AWS credentials not found. Configure AWS credentials.",
        ) from e
    except Exception as error:
        temp_path.unlink(missing_ok=True)
        LOG.error("Failed to download S3 file %s: %s", file_url, error)
        raise HTTPException(
            status_code=500, detail=f"Failed to download S3 file: {str(error)}"
        ) from error


async def download_file(
    file_url: str,
    max_size: int | None = None,
) -> tuple[str, str]:
    """Download/copy local file.

    Parameters
    ----------
    file_url : str
        File URL (file:///path/to/file).
    max_size : int | None, optional
        Maximum file size in bytes.

    Returns
    -------
    tuple[str, str]
        MD5 hash and temporary file path.

    Raises
    ------
    HTTPException
        If file operation fails or file is invalid.
    """

    if max_size is None:
        max_size = MAX_FILE_SIZE

    # Parse file URL: file:///path/to/file
    parsed = urlparse(file_url)
    file_path = Path(
        parsed.path
    ).resolve()  # Use resolve() to prevent path traversal

    if not file_path.is_absolute():
        raise HTTPException(
            status_code=400, detail="File URL must contain absolute path"
        )

    file_size = 0
    hash_md5 = hashlib.md5(usedforsecurity=False)

    # Create temporary file
    async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = Path(str(temp_file.name))

    try:
        # Check if source file exists
        if not await os.path.exists(file_path) or not await os.path.isfile(
            file_path
        ):
            raise HTTPException(status_code=404, detail="Source file not found")

        # Check file size
        stat_result = await os.stat(file_path)
        if stat_result.st_size > max_size:
            max_size_mb = f"{max_size / 1024 / 1024:.1f}"
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum size of {max_size_mb} MB",
            )

        first_chunk = True
        async with aiofiles.open(file_path, "rb") as src_f:
            async with aiofiles.open(temp_path, "wb") as dst_f:
                while True:
                    chunk = await src_f.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    file_size += len(chunk)

                    # Validate first chunk
                    if first_chunk:
                        await _validate_file_content(chunk, file_size, max_size)
                        first_chunk = False

                    hash_md5.update(chunk)
                    await dst_f.write(chunk)

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Source file is empty")

        LOG.info("Copied local file: %s (%d bytes)", file_url, file_size)
        return hash_md5.hexdigest(), str(temp_path)

    except HTTPException:
        temp_path.unlink(missing_ok=True)
        raise
    except Exception as error:
        temp_path.unlink(missing_ok=True)
        LOG.error("Failed to copy local file %s: %s", file_url, error)
        raise HTTPException(
            status_code=500, detail=f"Failed to copy local file: {str(error)}"
        ) from error


async def download_sftp_file(
    file_url: str,
    max_size: int | None = None,
) -> tuple[str, str]:
    """Download file from SFTP server.

    Parameters
    ----------
    file_url : str
        SFTP URL (sftp://user:pass@host:port/path/to/file).
    max_size : int, optional
        Maximum file size in bytes.

    Returns
    -------
    tuple[str, str]
        MD5 hash and temporary file path.

    Raises
    ------
    HTTPException
        If download fails or file is invalid.
    """
    if max_size is None:
        max_size = MAX_FILE_SIZE

    # Parse SFTP URL
    parsed = urlparse(file_url)

    host = parsed.hostname
    port = parsed.port or 22
    username = parsed.username
    password = parsed.password
    remote_path = parsed.path

    if not host or not remote_path:
        msg = (
            "Invalid SFTP URL format. "
            "Expected: sftp://[user[:pass]@]host[:port]/path"
        )
        raise HTTPException(status_code=400, detail=msg)

    file_size = 0
    hash_md5 = hashlib.md5(usedforsecurity=False)

    # Create temporary file
    async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = Path(str(temp_file.name))

    try:
        # Connect to SFTP server
        connect_kwargs: dict[str, str | int] = {"host": host, "port": port}
        if username:
            connect_kwargs["username"] = username
        if password:
            connect_kwargs["password"] = password

        async with asyncssh.connect(**connect_kwargs) as conn:
            async with conn.start_sftp_client() as sftp:
                # Check if remote file exists and get attributes
                try:
                    attrs = await sftp.stat(remote_path)
                    if attrs.size and attrs.size > max_size:
                        max_size_mb = f"{max_size / 1024 / 1024:.1f}"
                        msg = f"File exceeds maximum size of {max_size_mb} MB"
                        raise HTTPException(
                            status_code=400,
                            detail=msg,
                        )
                except asyncssh.SFTPNoSuchFile as e:
                    LOG.error("SFTP file not found: %s", remote_path)
                    raise HTTPException(
                        status_code=404, detail="Remote file not found"
                    ) from e

                # Download file in chunks
                first_chunk = True
                async with sftp.open(remote_path, "rb") as remote_f:
                    async with aiofiles.open(temp_path, "wb") as local_f:
                        while True:
                            chunk: bytes = await remote_f.read(CHUNK_SIZE)
                            if not chunk:
                                break

                            if isinstance(chunk, str):  # pragma: no cover
                                chunk = chunk.encode("utf-8")

                            file_size += len(chunk)

                            # Validate first chunk
                            if first_chunk:
                                await _validate_file_content(
                                    chunk, file_size, max_size
                                )
                                first_chunk = False

                            hash_md5.update(chunk)
                            await local_f.write(chunk)

        if file_size == 0:
            raise HTTPException(
                status_code=400, detail="Downloaded file is empty"
            )

        LOG.info("Downloaded SFTP file: %s (%d bytes)", file_url, file_size)
        return hash_md5.hexdigest(), str(temp_path)

    except HTTPException:
        temp_path.unlink(missing_ok=True)
        raise
    except Exception as error:
        temp_path.unlink(missing_ok=True)
        LOG.error("Failed to download SFTP file %s: %s", file_url, error)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download SFTP file: {str(error)}",
        ) from error


async def download_ftp_file(
    file_url: str,
    max_size: int | None = None,
) -> tuple[str, str]:
    """Download file from FTP server.

    Parameters
    ----------
    file_url : str
        FTP URL (ftp://user:pass@host:port/path/to/file).
    max_size : int | None
        Maximum file size in bytes.

    Returns
    -------
    tuple[str, str]
        MD5 hash and temporary file path.

    Raises
    ------
    HTTPException
        If download fails or file is invalid.
    StatusCodeError
        If remote file does not exist or exceeds size limit.
    """
    if max_size is None:
        max_size = MAX_FILE_SIZE

    # Parse FTP URL
    parsed = urlparse(file_url)

    host = parsed.hostname
    port = parsed.port or 21
    username = parsed.username or "anonymous"
    password = parsed.password or ""
    remote_path = parsed.path

    if not host or not remote_path:
        msg = (
            "Invalid FTP URL format. "
            "Expected: ftp://[user[:pass]@]host[:port]/path"
        )
        raise HTTPException(
            status_code=400,
            detail=msg,
        )

    file_size = 0
    hash_md5 = hashlib.md5(usedforsecurity=False)

    # Create temporary file
    async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = Path(str(temp_file.name))

    try:
        # Connect to FTP server
        async with aioftp.Client.context(host, port, username, password) as ftp:
            # Check if remote file exists
            try:
                stat = await ftp.stat(remote_path)
                if (
                    hasattr(stat, "size")
                    and int(getattr(stat, "size")) > max_size
                ):
                    max_size_mb = f"{max_size / 1024 / 1024:.1f}"
                    raise HTTPException(
                        status_code=400,
                        detail=f"File exceeds maximum size of {max_size_mb} MB",
                    )
            except aioftp.StatusCodeError as e:
                if "550" in e.received_codes:  # File not found
                    raise HTTPException(
                        status_code=404, detail="Remote file not found"
                    ) from e
                raise

            # FIXED: Download file with correct async context manager usage
            first_chunk = True
            stream = await ftp.download_stream(remote_path)
            async with stream:
                async with aiofiles.open(temp_path, "wb") as f:
                    async for chunk in stream.iter_by_block(CHUNK_SIZE):
                        if not chunk:
                            continue

                        file_size += len(chunk)

                        # Validate first chunk
                        if first_chunk:
                            await _validate_file_content(
                                chunk, file_size, max_size
                            )
                            first_chunk = False
                        elif file_size > max_size:
                            max_size_mb = f"{max_size / 1024 / 1024:.1f}"
                            msg = (
                                f"File exceeds maximum size of {max_size_mb} MB"
                            )
                            raise HTTPException(
                                status_code=400,
                                detail=msg,
                            )

                        hash_md5.update(chunk)
                        await f.write(chunk)

        if file_size == 0:
            raise HTTPException(
                status_code=400, detail="Downloaded file is empty"
            )

        LOG.info("Downloaded FTP file: %s (%d bytes)", file_url, file_size)
        return hash_md5.hexdigest(), str(temp_path)

    except HTTPException:
        temp_path.unlink(missing_ok=True)
        raise
    except Exception as error:
        temp_path.unlink(missing_ok=True)
        LOG.error("Failed to download FTP file %s: %s", file_url, error)
        raise HTTPException(
            status_code=500, detail=f"Failed to download FTP file: {str(error)}"
        ) from error
