# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Local filesystem-based storage backend."""

# We might later want to add more backends like S3 (with boto?).
# and a factory to select one (Depends) based on the configuration/settings.
# for now, let's keep it simple and local.

import hashlib
import logging
import shutil
import tempfile
from pathlib import Path
from typing import List, Tuple

import aiofiles
import puremagic
from aiofiles import os
from fastapi import BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from .common import ALLOWED_MIME_TYPES, CHUNK_SIZE, MAX_FILE_SIZE

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
        self.root_dir = root_dir
        self.root_dir.mkdir(exist_ok=True, parents=True)

    # pylint: disable=unused-argument,no-self-use
    async def save_file(
        self,
        parent_name: str,
        file: UploadFile,
    ) -> Tuple[str, str]:
        """Save an uploaded file to a temporary location and return its path.

        Parameters
        ----------
        parent_name : str
            The parent folder name (unused).
        file : UploadFile
            The file to save.

        Returns
        -------
        Tuple[str, str]
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
            temp_path.unlink(missing_ok=True)
            raise

        except Exception as error:  # pragma: no cover
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file: {str(error)}",
            ) from error

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
        full_dst_path = self.root_dir / dst_path
        await os.makedirs(full_dst_path.parent, exist_ok=True)
        if full_dst_path.exists():
            raise HTTPException(
                status_code=400, detail="Destination file already exists"
            )
        move = os.wrap(shutil.move)
        try:
            await move(src_path, full_dst_path)
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
        await os.makedirs(parent_path, exist_ok=True)

        async def cleanup(temp_dir: str | None) -> None:
            """Clean up the temporary directory.

            Parameters
            ----------
            temp_dir : str | None
                The temporary directory.
            """
            if temp_dir and await os.path.isdir(temp_dir):
                rmtree = os.wrap(shutil.rmtree)
                await rmtree(str(temp_dir), ignore_errors=True)

        temp_dir: str | None = None
        # pylint: disable=too-many-try-statements, broad-exception-caught
        # pylint: disable=consider-using-with
        try:
            # async with aiofiles.tempfile.TemporaryDirectory(
            #     delete=False  # this cannot work with aiofiles
            #      (no overload for delete=False)
            # ) as tempdir:
            temp_dir = temp_dir = tempfile.mkdtemp()
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
        full_src_path = self.root_dir / src_path
        full_dest_path = self.root_dir / dest_path
        src = Path(full_src_path).resolve()
        dest = Path(full_dest_path).resolve()
        if not await os.path.exists(src) or not await os.path.isfile(src):
            raise HTTPException(status_code=404, detail="Source file not found")
        if await os.path.exists(dest) and await os.path.isfile(dest):
            raise HTTPException(
                status_code=400, detail="Destination file already exists"
            )
        copyfile = os.wrap(shutil.copyfile)
        # pylint: disable=too-many-try-statements, broad-exception-caught
        try:
            await copyfile(str(src), str(dest))
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
        full_src_path = self.root_dir / src_path
        full_dest_path = self.root_dir / dest_path
        src = Path(full_src_path).resolve()
        dest = Path(full_dest_path).resolve()
        if not await os.path.exists(src) or not await os.path.isdir(src):
            raise HTTPException(
                status_code=404, detail="Source folder not found"
            )
        if await os.path.exists(dest) and await os.path.isdir(dest):
            raise HTTPException(
                status_code=400, detail="Destination folder already exists"
            )
        copytree = os.wrap(shutil.copytree)
        # pylint: disable=too-many-try-statements, broad-exception-caught
        try:
            await copytree(str(src), str(dest))
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
        full_path = self.root_dir / path
        file_path = Path(full_path).resolve()
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
        full_folder_path = self.root_dir / folder_path
        folder = Path(full_folder_path).resolve()
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

    async def list_files(self, folder_path: str) -> List[str]:
        """List all files in a folder.

        Parameters
        ----------
        folder_path : str
            The folder path.

        Returns
        -------
        List[str]
            List of file paths.

        Raises
        ------
        HTTPException
            If an error occurs.
        """
        folder = Path(folder_path).resolve()
        if not await os.path.exists(folder) or not await os.path.isdir(folder):
            folder = (self.root_dir / folder_path).resolve()
        if not await os.path.exists(folder) or not await os.path.isdir(folder):
            LOG.warning("Folder not found: %s", folder)
            return []

        async def folder_tree(folder: str, max_depth: int = 10) -> List[str]:
            """List files recursively in a folder.

            Parameters
            ----------
            folder : str
                The folder to list.
            max_depth : int
                The maximum recursion depth.

            Returns
            -------
            List[str]
                List of file paths.
            """
            files: List[str] = []
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

        return await folder_tree(str(folder))
