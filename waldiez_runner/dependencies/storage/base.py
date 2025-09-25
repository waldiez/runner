# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pyright: reportReturnType=false

"""Base storage protocol."""

from typing import Protocol, runtime_checkable

from fastapi import BackgroundTasks, UploadFile
from fastapi.responses import FileResponse, StreamingResponse


@runtime_checkable
class Storage(Protocol):
    """Base file service."""

    async def resolve(
        self,
        path: str,
    ) -> str | None:
        """Resolve a file path.

        Parameters
        ----------
        path : str
            The path to resolve.

        Returns
        -------
        str | None
            The resolved path if resolved, else None
        """

    async def save_file(
        self,
        parent_name: str,
        file: UploadFile,
    ) -> tuple[str, str]:
        """Save an uploaded file to a temporary location and return its path.

        Parameters
        ----------
        parent_name : str
            The parent folder name
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

    async def get_file_from_url(
        self,
        file_url: str,
    ) -> tuple[str, str]:
        """Download a file from a URL and save it to a temporary location.

        Parameters
        ----------
        file_url : str
            The URL of the file.

        Returns
        -------
        tuple[str, str]
            The MD5 hash and the temporary file path.

        Raises
        ------
        HTTPException
            If the file is invalid or an error occurs.
        """

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
        """
