# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pyright: reportUnknownMemberType=false,reportUnusedParameter=false

"""Local filesystem-based storage backend."""

# We might later want to add more backends like S3 (with boto?).
# and a factory to select one (Depends) based on the configuration/settings.
# for now, let's keep it simple and local.

import hashlib
import logging
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import aiofiles
import anyio.to_thread
import puremagic
from aiofiles import os
from fastapi import BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from .utils import (  # download_gcs_file,
    ALLOWED_MIME_TYPES,
    CHUNK_SIZE,
    MAX_FILE_SIZE,
    download_file,
    download_ftp_file,
    download_http_file,
    download_s3_file,
    download_sftp_file,
)

LOG = logging.getLogger(__name__)


class LocalStorage:
    """Local filesystem-based storage backend."""

    def __init__(self, root_dir: Path) -> None:
        """Initialize the service.

        Parameters
        ----------
        root_dir : Path
            The root directory.
        """
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(exist_ok=True, parents=True)

    async def _resolve(self, path: str) -> Path:
        """Resolve a path."""
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = self.root_dir / path.lstrip("/")
        return await anyio.to_thread.run_sync(
            lambda: resolved.resolve().absolute()
        )

    async def resolve(self, path: str) -> str | None:
        """Resolve a file path.

        Parameters
        ----------
        path : str
            The path to resolve.

        Returns
        -------
        str | None
            The resolved path.
        """
        resolved = await self._resolve(path)
        if not resolved.exists():
            return None
        return str(resolved)

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except BaseException:  # pylint: disable=broad-exception-caught
            pass

    @staticmethod
    async def unlink(path: Path) -> None:
        """Remove a file.

        Parameters
        ----------
        path : Path
            The path to remove.
        """
        await anyio.to_thread.run_sync(LocalStorage._unlink, path)

    # pylint: disable=unused-argument,no-self-use
    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    async def save_file(
        self,
        parent_name: str,
        file: UploadFile,
    ) -> tuple[str, str]:
        """Save an uploaded file to a temporary location and return its path.

        Parameters
        ----------
        parent_name : str
            The parent folder name (unused).
        file : UploadFile
            The file to save.

        Returns
        -------
        tuple[str, str]
            The MD5 hash and the temporary file path.

        Raises
        ------
        HTTPException
            If the file is invalid or an error occurs.
        """
        file_size = 0
        max_size_mb = f"{MAX_FILE_SIZE / 1024 / 1024}"
        too_large_message = f"File exceeds maximum size of {max_size_mb} MB"

        hash_md5 = hashlib.md5(usedforsecurity=False)

        async with aiofiles.tempfile.NamedTemporaryFile(
            delete=False
        ) as temp_file:
            temp_path = Path(str(temp_file.name))
        # pylint: disable=too-many-try-statements, broad-exception-caught
        try:
            async with aiofiles.open(temp_path, "wb") as f:
                first_chunk = await file.read(2048)
                if not first_chunk:
                    raise HTTPException(
                        status_code=400, detail="Uploaded file is empty"
                    )
                detected_mime = puremagic.from_string(first_chunk, mime=True)
                if not detected_mime:
                    raise HTTPException(
                        status_code=400, detail="Could not detect MIME type"
                    )
                if detected_mime not in ALLOWED_MIME_TYPES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid file type: {detected_mime}",
                    )

                file_size += len(first_chunk)
                hash_md5.update(first_chunk)
                await f.write(first_chunk)

                while chunk := await file.read(CHUNK_SIZE):
                    file_size += len(chunk)
                    if file_size > MAX_FILE_SIZE:
                        raise HTTPException(
                            status_code=400, detail=too_large_message
                        )

                    hash_md5.update(chunk)
                    await f.write(chunk)

            return hash_md5.hexdigest(), str(temp_path)

        except HTTPException:
            await self.unlink(temp_path)
            raise

        except Exception as error:  # pragma: no cover
            await self.unlink(temp_path)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file: {str(error)}",
            ) from error

    # pylint: disable=unused-argument,no-self-use, too-many-try-statements
    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    async def get_file_from_url(
        self,
        file_url: str,
        allowed_extensions: list[str] | None = None,
        max_size: int | None = None,
    ) -> tuple[str, str]:
        """Download a file from a URL and save it to a temporary location.

        Parameters
        ----------
        file_url : str
            The URL of the file to download.
        allowed_extensions : list[str], optional
            List of allowed file extensions for validation.
        max_size : int, optional
            Maximum file size in bytes. Defaults to MAX_FILE_SIZE.

        Returns
        -------
        tuple[str, str]
            The MD5 hash and the temporary file path.

        Raises
        ------
        HTTPException
            If the file is invalid, too large, or download fails.
        """
        if max_size is None:
            max_size = MAX_FILE_SIZE
        parsed_url = urlparse(file_url)
        if parsed_url.scheme.lower() == "s3":
            return await download_s3_file(file_url, max_size)
        # if parsed_url.scheme.lower() == "gs":
        #     return await download_gcs_file(file_url, max_size)
        if parsed_url.scheme.lower() in ("http", "https"):
            return await download_http_file(file_url, max_size)
        if parsed_url.scheme.lower() == "file":
            return await download_file(file_url, max_size)
        if parsed_url.scheme.lower() == "sftp":
            return await download_sftp_file(file_url, max_size)
        if parsed_url.scheme.lower() == "ftp":
            return await download_ftp_file(file_url, max_size)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported URL scheme: {parsed_url.scheme}",
        )

    async def move_file(
        self,
        src_path: str,
        dst_path: str,
    ) -> None:
        """Move a file to the task folder.

        Parameters
        ----------
        src_path : str
            The source file path.
        dst_path : str
            The destination file path.

        Raises
        ------
        HTTPException
            If an error occurs.
        """
        full_src_path = await self._resolve(src_path)
        full_dst_path = await self._resolve(dst_path)

        if not full_src_path.exists() or not full_src_path.is_file():
            raise HTTPException(status_code=404, detail="Source file not found")
        if full_dst_path.exists():
            raise HTTPException(
                status_code=400, detail="Destination file already exists"
            )
        await os.makedirs(full_dst_path.parent, exist_ok=True)

        move = os.wrap(shutil.move)
        try:
            await move(full_src_path, full_dst_path)
        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to move file: {str(error)}",
            ) from error

    async def download_archive(
        self,
        parent_folder: str,
        folder_name: str,
        background_tasks: BackgroundTasks,
    ) -> FileResponse | StreamingResponse:
        """Download task folder as a zip archive.

        Parameters
        ----------
        parent_folder : str
            The parent folder.
        folder_name : str
            The folder name.
        background_tasks : BackgroundTasks
            Background tasks.

        Returns
        -------
        FileResponse | StreamingResponse
            The response.

        Raises
        ------
        HTTPException
            If an error occurs.
        """
        full_parent_folder = self.root_dir / parent_folder
        parent_path = Path(full_parent_folder).resolve()
        if not await os.path.isdir(parent_path):
            raise HTTPException(
                status_code=400, detail="Invalid archive directory"
            )
        await os.makedirs(parent_path, exist_ok=True)

        async def cleanup(tmp_dir: str | None) -> None:
            """Clean up the temporary directory.

            Parameters
            ----------
            tmp_dir : str | None
                The temporary directory.
            """
            if tmp_dir and await os.path.isdir(tmp_dir):
                rmtree = os.wrap(shutil.rmtree)
                await rmtree(str(tmp_dir), ignore_errors=True)

        temp_dir: str | None = None
        # pylint: disable=too-many-try-statements, broad-exception-caught
        # pylint: disable=consider-using-with
        try:
            temp_dir = tempfile.mkdtemp()
            zip_path = Path(temp_dir) / f"{folder_name}.zip"
            make_archive = os.wrap(shutil.make_archive)
            archive = await make_archive(
                base_name=str(zip_path.with_suffix("")),
                format="zip",
                root_dir=str(parent_path),
                base_dir=folder_name,
            )
            content_disposition = f"attachment; filename={zip_path.name}"
            background_tasks.add_task(cleanup, temp_dir)
            return FileResponse(
                archive,
                filename=zip_path.name,
                media_type="application/zip",
                background=background_tasks,
                headers={
                    "Content-Disposition": content_disposition,
                    "X-Accel-Buffering": "no",
                },
            )
        except (FileNotFoundError, NotADirectoryError) as error:
            LOG.error("Failed to generate archive: %s", error)
            msg = "Failed to generate archive"
            await cleanup(temp_dir)
            raise HTTPException(status_code=500, detail=msg) from error

        except BaseException as error:
            LOG.error("Failed to download archive: %s", error)
            msg = "Failed to download archive"
            await cleanup(temp_dir)
            raise HTTPException(status_code=500, detail=msg) from error

    async def copy_file(self, src_path: str, dest_path: str) -> None:
        """Copy a file from `src_path` to `dest_path`.

        Parameters
        ----------
        src_path : str
            Source path.
        dest_path : str
            Destination path.

        Raises
        ------
        HTTPException
            If an error occurs.
        """
        full_src_path = await self._resolve(src_path)
        if not full_src_path.exists() or not full_src_path.is_file():
            raise HTTPException(status_code=404, detail="Source file not found")
        full_dest_path = await self._resolve(dest_path)
        if not full_src_path.exists() or not full_src_path.is_file():
            raise HTTPException(status_code=404, detail="Source file not found")
        if full_dest_path.exists():
            raise HTTPException(
                status_code=400, detail="Destination file already exists"
            )
        await os.makedirs(full_dest_path.parent, exist_ok=True)
        copyfile = os.wrap(shutil.copyfile)
        # pylint: disable=too-many-try-statements, broad-exception-caught
        try:
            await copyfile(str(full_src_path), str(full_dest_path))
        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to copy file: {str(error)}",
            ) from error

    async def copy_folder(self, src_path: str, dest_path: str) -> None:
        """Copy a folder from `src_path` to `dest_path`.

        Parameters
        ----------
        src_path : str
            Source path.
        dest_path : str
            Destination path.
        Raises
        ------
        HTTPException
            If an error occurs.
        """
        full_src_path = await self._resolve(src_path)
        full_dest_path = await self._resolve(dest_path)
        await os.makedirs(full_dest_path.parent, exist_ok=True)
        if not await os.path.exists(full_src_path) or not await os.path.isdir(
            full_src_path
        ):
            raise HTTPException(
                status_code=404, detail="Source folder not found"
            )
        if await os.path.exists(full_dest_path) and await os.path.isdir(
            full_dest_path
        ):
            raise HTTPException(
                status_code=400, detail="Destination folder already exists"
            )
        copytree = os.wrap(shutil.copytree)
        # pylint: disable=too-many-try-statements, broad-exception-caught
        try:
            await copytree(str(full_src_path), str(full_dest_path))
        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to copy folder: {str(error)}",
            ) from error

    async def delete_file(self, path: str) -> None:
        """Delete a file.

        Parameters
        ----------
        path : str
            The file path.

        Raises
        ------
        HTTPException
            If an error occurs.
        """
        file_path = await self._resolve(path)
        if not await os.path.exists(file_path) or not await os.path.isfile(
            file_path
        ):
            LOG.warning("File not found: %s", file_path)
            return
        # pylint: disable=too-many-try-statements, broad-exception-caught
        try:
            await os.unlink(str(file_path))
        except Exception as error:
            LOG.error("Failed to delete file: %s", error)
            raise HTTPException(
                status_code=500,
                detail="Failed to delete file",
            ) from error

    async def delete_folder(self, folder_path: str) -> None:
        """Delete a folder and its contents.

        Parameters
        ----------
        folder_path : str
            The folder path.

        Raises
        ------
        HTTPException
            If an error occurs.
        """
        folder = await self._resolve(folder_path)
        if not await os.path.exists(folder) or not await os.path.isdir(folder):
            LOG.warning("Folder not found: %s", folder)
            return
        rmtree = os.wrap(shutil.rmtree)
        # pylint: disable=too-many-try-statements, broad-exception-caught
        try:
            await rmtree(str(folder), ignore_errors=True)
        except Exception as error:
            LOG.error("Failed to delete folder: %s", error)
            raise HTTPException(
                status_code=500,
                detail="Failed to delete folder",
            ) from error

    async def list_files(self, folder_path: str) -> list[str]:
        """List all files in a folder.

        Parameters
        ----------
        folder_path : str
            The folder path.

        Returns
        -------
        list[str]
            List of file paths.

        Raises
        ------
        HTTPException
            If an error occurs.
        """
        root = await self._resolve(folder_path)
        if not await os.path.exists(root) or not await os.path.isdir(root):
            LOG.warning("Folder not found: %s", root)
            return []

        async def folder_tree(folder: str, max_depth: int = 10) -> list[str]:
            """List files recursively in a folder.

            Parameters
            ----------
            folder : str
                The folder to list.
            max_depth : int
                The maximum recursion depth.

            Returns
            -------
            list[str]
                List of file paths.
            """
            files: list[str] = []
            if max_depth < 0:
                return files
            for item in await os.listdir(folder):
                full_path = str(Path(folder) / item)
                if await os.path.isdir(full_path):
                    sub_files = await folder_tree(full_path, max_depth - 1)
                    entries = [f"{item}/{sub}" for sub in sub_files]
                    files.extend(entries)
                else:
                    files.append(item)
            return files

        return await folder_tree(str(root))

    async def exists(self, path: str) -> bool:
        """Check if an item exists in the storage.

        Parameters
        ----------
        path : str
            The path to check.

        Returns
        -------
        bool
            True if the item exists, False otherwise.
        """

        return await os.path.exists(Path(path))

    async def is_file(self, path: str) -> bool:
        """Check if an item exists and is a file in the storage.

        Parameters
        ----------
        path : str
            The path to check.

        Returns
        -------
        bool
            True if the item exists and is a file, False otherwise.
        """
        return await os.path.isfile(await self._resolve(path))

    async def is_dir(self, path: str) -> bool:
        """Check if an item exists and is a directory in the storage.

        Parameters
        ----------
        path : str
            The path to check.

        Returns
        -------
        bool
            True if the item exists and is a directory, False otherwise.
        """
        return await os.path.isdir(await self._resolve(path))

    async def hash(self, path: str) -> str:
        """Get the file's md5 hash.

        Parameters
        ----------
        path : str
            The path to the file.

        Returns
        -------
        str
            The file's md5 hash.

        Raises
        ------
        HTTPException
            If the file doesn't exist or cannot be read.
        """
        file_path = await self._resolve(path)

        if not await os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        if not await os.path.isfile(file_path):
            raise HTTPException(status_code=400, detail="Path is not a file")

        hash_md5 = hashlib.md5(usedforsecurity=False)

        try:
            async with aiofiles.open(file_path, "rb") as f:
                while chunk := await f.read(CHUNK_SIZE):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to compute file hash: {str(error)}",
            ) from error
