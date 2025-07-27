# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-return-doc,missing-yield-doc

"""Test waldiez_runner.dependencies.storage.local*."""

import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile

from waldiez_runner.dependencies.storage.local import (
    MAX_FILE_SIZE,
    LocalStorage,
)

FILE_EXTENSION = ".waldiez"


@pytest.fixture(name="storage")
def storage_fixture(tmp_path: Path) -> LocalStorage:
    """Get a LocalStorage instance."""
    return LocalStorage(root_dir=tmp_path)


@pytest.fixture(name="upload_file")
def upload_file_fixture() -> UploadFile:
    """Get a sample UploadFile instance."""
    content = b'{"key": "value"}'
    file = UploadFile(filename=f"test.{FILE_EXTENSION}", file=BytesIO(content))
    return file


@pytest.mark.anyio
async def test_save_file(
    storage: LocalStorage,
    upload_file: UploadFile,
) -> None:
    """Test saving a file."""
    md5, tmp_path = await storage.save_file("client", upload_file)

    assert Path(tmp_path).exists()
    assert len(md5) == 32


@pytest.mark.anyio
async def test_move_file(storage: LocalStorage, tmp_path: Path) -> None:
    """Test moving a file."""
    src_path = tmp_path / "src.json"
    dst_path = tmp_path / "dst.json"

    src_path.write_text('{"key": "value"}')

    await storage.move_file(str(src_path), str(dst_path))

    assert not src_path.exists()
    assert dst_path.exists()


@pytest.mark.anyio
async def test_copy_file(storage: LocalStorage, tmp_path: Path) -> None:
    """Test copying a file."""
    src_path = tmp_path / "src.json"
    dst_path = tmp_path / "dst.json"

    src_path.write_text('{"key": "value"}')

    await storage.copy_file(str(src_path), str(dst_path))

    assert src_path.exists()
    assert dst_path.exists()


@pytest.mark.anyio
async def test_delete_file(storage: LocalStorage, tmp_path: Path) -> None:
    """Test deleting a file."""
    file_path = tmp_path / "file.json"
    file_path.write_text('{"key": "value"}')

    await storage.delete_file(str(file_path))

    assert not file_path.exists()


@pytest.mark.anyio
async def test_delete_folder(storage: LocalStorage, tmp_path: Path) -> None:
    """Test deleting a folder."""
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "file.json").write_text('{"key": "value"}')

    await storage.delete_folder(str(folder))

    assert not folder.exists()


@pytest.mark.anyio
async def test_list_files(storage: LocalStorage, tmp_path: Path) -> None:
    """Test listing files."""
    (tmp_path / "file1.json").write_text('{"key": "value"}')
    (tmp_path / "file2.json").write_text('{"key": "value"}')
    sub_folder = tmp_path / "sub_folder"
    sub_folder.mkdir()
    (sub_folder / "file3.json").write_text('{"key": "value"}')
    sub_sub_folder = sub_folder / "sub_sub_folder"
    sub_sub_folder.mkdir()
    (sub_sub_folder / "file4.json").write_text('{"key": "value"}')

    files = await storage.list_files(str(tmp_path))

    assert len(files) == 4


@pytest.mark.anyio
async def test_download_archive(storage: LocalStorage, tmp_path: Path) -> None:
    """Test downloading an archive."""
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "file1.json").write_text('{"key": "value"}')
    (folder / "file2.json").write_text('{"key": "value"}')

    background_tasks = BackgroundTasks()

    response = await storage.download_archive(
        str(tmp_path), "folder", background_tasks
    )

    assert response.status_code == 200
    assert response.media_type in (
        "application/zip",
        "application/x-zip-compressed",
    )


@pytest.mark.anyio
async def test_save_file_empty(
    storage: LocalStorage, upload_file: UploadFile
) -> None:
    """Test saving an empty file."""
    upload_file.file = BytesIO(b"")

    with pytest.raises(HTTPException) as exc_info:
        await storage.save_file("client", upload_file)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Uploaded file is empty"


@pytest.mark.anyio
async def test_save_file_invalid_mime(
    storage: LocalStorage,
    upload_file: UploadFile,
    tmp_path: Path,
) -> None:
    """Test saving a file with invalid MIME type."""
    # make a zip in tmp_path
    zip_path = tmp_path / "test_save_file_invalid_mime.zip"
    with zipfile.ZipFile(zip_path, "w") as zip_file:
        zip_file.writestr("test.txt", "test")

    upload_file.file = zip_path.open("rb")
    upload_file.filename = "test_save_file_invalid_mime.zip"

    with pytest.raises(HTTPException) as exc_info:
        await storage.save_file("client", upload_file)

    assert exc_info.value.status_code == 400
    assert "Invalid file type" in exc_info.value.detail
    try:
        zip_path.unlink(missing_ok=True)
    except (OSError, PermissionError):
        pass


@pytest.mark.anyio
async def test_save_file_too_large(storage: LocalStorage) -> None:
    """Test saving a file that is too large."""
    first_part = b'{"nested": {"deep": "data"}, "array": ['
    repeat_part = b'{"k": "v"},' * 10_000_000
    last_part = b"{}]}"
    large_json_like_content = first_part + repeat_part + last_part
    # noinspection PyTypeChecker
    upload_file = UploadFile(
        file=BytesIO(large_json_like_content),
        filename="large_file.json",
        headers={"content-type": "application/json"},  # pyright: ignore
    )

    with patch("puremagic.from_string", return_value="application/json"):
        with pytest.raises(HTTPException) as exc_info:
            await storage.save_file("client", upload_file)

    assert exc_info.value.status_code == 400
    max_size_mb = MAX_FILE_SIZE / 1024 / 1024
    assert (
        exc_info.value.detail
        == f"File exceeds maximum size of {max_size_mb} MB"
    )


@pytest.mark.anyio
async def test_move_file_failure(storage: LocalStorage, tmp_path: Path) -> None:
    """Test moving a file."""
    src_path = tmp_path / "test_move_file_failure_src.json"
    dst_path = tmp_path / "test_move_file_failure_dst.json"

    src_path.write_text('{"key": "value"}')
    dst_path.write_text('{"key": "value"}')

    with pytest.raises(HTTPException) as exc_info:
        await storage.move_file(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Destination file already exists"


@pytest.mark.anyio
async def test_move_file_error(storage: LocalStorage, tmp_path: Path) -> None:
    """Test moving a file."""
    src_path = tmp_path / "test_move_file_error_src.json"
    dst_path = tmp_path / "test_move_file_error_dst.json"

    src_path.write_text('{"key": "value"}')

    with patch("shutil.move", side_effect=OSError):
        with pytest.raises(HTTPException) as exc_info:
            await storage.move_file(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail.startswith("Failed to move file:")


@pytest.mark.anyio
async def test_copy_file_failure(storage: LocalStorage, tmp_path: Path) -> None:
    """Test copying a file."""
    src_path = tmp_path / "test_copy_file_failure_src.json"
    dst_path = tmp_path / "test_copy_file_failure_dst.json"

    src_path.write_text('{"key": "value"}')
    dst_path.write_text('{"key": "value"}')

    with pytest.raises(HTTPException) as exc_info:
        await storage.copy_file(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Destination file already exists"


@pytest.mark.anyio
async def test_copy_file_src_not_found(
    storage: LocalStorage, tmp_path: Path
) -> None:
    """Test copying a file."""
    src_path = tmp_path / "test_copy_file_src_not_found_src.json"
    dst_path = tmp_path / "test_copy_file_src_not_found_dst.json"

    with pytest.raises(HTTPException) as exc_info:
        await storage.copy_file(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Source file not found"


@pytest.mark.anyio
async def test_copy_file_error(storage: LocalStorage, tmp_path: Path) -> None:
    """Test copying a file."""
    src_path = tmp_path / "test_copy_file_error_src.json"
    dst_path = tmp_path / "test_copy_file_error_dst.json"

    src_path.write_text('{"key": "value"}')

    with patch("shutil.copyfile", side_effect=OSError):
        with pytest.raises(HTTPException) as exc_info:
            await storage.copy_file(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail.startswith("Failed to copy file:")


@pytest.mark.anyio
async def test_download_archive_failure(
    storage: LocalStorage, tmp_path: Path
) -> None:
    """Test downloading an archive."""
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "file1.json").write_text('{"key": "value"}')
    (folder / "file2.json").write_text('{"key": "value"}')

    background_tasks = BackgroundTasks()

    with patch("shutil.make_archive", side_effect=OSError):
        with pytest.raises(HTTPException) as exc_info:
            await storage.download_archive(
                str(tmp_path), "folder", background_tasks
            )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail.startswith("Failed to download archive")


@pytest.mark.anyio
async def test_download_archive_not_found(
    storage: LocalStorage, tmp_path: Path
) -> None:
    """Test downloading an archive."""
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as exc_info:
        await storage.download_archive(
            str(tmp_path), "folder", background_tasks
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to generate archive"


@pytest.mark.anyio
async def test_delete_file_not_found(
    storage: LocalStorage, tmp_path: Path
) -> None:
    """Test deleting a file."""
    file_path = tmp_path / "test_delete_file_not_found.json"
    assert not file_path.exists()
    await storage.delete_file(str(file_path))


@pytest.mark.anyio
async def test_delete_file_failure(
    storage: LocalStorage, tmp_path: Path
) -> None:
    """Test deleting a file."""
    file_path = tmp_path / "test_delete_file_failure.json"
    file_path.write_text('{"key": "value"}')

    with patch("aiofiles.os.unlink", side_effect=OSError):
        with pytest.raises(HTTPException) as exc_info:
            await storage.delete_file(str(file_path))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail.startswith("Failed to delete file")


@pytest.mark.anyio
async def test_delete_folder_not_found(
    storage: LocalStorage, tmp_path: Path
) -> None:
    """Test deleting a folder."""
    folder = tmp_path / "test_delete_folder_not_found"
    assert not folder.exists()
    await storage.delete_folder(str(folder))


@pytest.mark.anyio
async def test_delete_folder_failure(
    storage: LocalStorage, tmp_path: Path
) -> None:
    """Test deleting a folder."""
    folder = tmp_path / "test_delete_folder_failure"
    folder.mkdir()
    (folder / "file.json").write_text('{"key": "value"}')

    with patch("shutil.rmtree", side_effect=OSError):
        with pytest.raises(HTTPException) as exc_info:
            await storage.delete_folder(str(folder))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail.startswith("Failed to delete folder")


@pytest.mark.anyio
async def test_list_files_not_found(
    storage: LocalStorage, tmp_path: Path
) -> None:
    """Test listing files."""
    folder = tmp_path / "test_list_files_not_found"
    assert not folder.exists()
    files = await storage.list_files(str(folder))
    assert not files
