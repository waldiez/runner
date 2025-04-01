# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Base storage protocol."""

from typing import List, Protocol, Tuple, runtime_checkable

from fastapi import BackgroundTasks, UploadFile
from fastapi.responses import FileResponse, StreamingResponse


@runtime_checkable
class Storage(Protocol):
    """Base file service."""

    async def save_file(
        self,
        parent_name: str,
        file: UploadFile,
    ) -> Tuple[str, str]:
        """Save an uploaded file to a temporary location and return its path.

        Parameters
        ----------
        parent_name : str
            The parent folder name
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
