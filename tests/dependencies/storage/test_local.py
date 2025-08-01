# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=missing-param-doc,missing-return-doc,missing-yield-doc
# pylint: disable=protected-access
# pyright: reportPrivateUsage=false

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
async def test_get_file_from_url_validation_error(
    storage: LocalStorage,
) -> None:
    """Test get_file_from_url with URL validation error."""
    # Mock get_filename_from_url to raise a non-HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await storage.get_file_from_url("invalid://url")

    assert exc_info.value.status_code == 400
    assert "Unsupported URL scheme" in exc_info.value.detail


@pytest.mark.anyio
async def test_move_file_source_not_found(storage: LocalStorage) -> None:
    """Test moving a non-existent source file."""
    src_path = storage.root_dir / "nonexistent_source.json"
    dst_path = storage.root_dir / "destination.json"

    with pytest.raises(HTTPException) as exc_info:
        await storage.move_file(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Source file not found"


@pytest.mark.anyio
async def test_download_archive_base_exception(storage: LocalStorage) -> None:
    """Test download_archive with BaseException."""
    folder = storage.root_dir / "test_download_archive_base_exception"
    folder.mkdir()
    (folder / "file.txt").write_text("test")

    background_tasks = BackgroundTasks()

    # Mock make_archive to raise BaseException
    with patch(
        "shutil.make_archive", side_effect=KeyboardInterrupt("Interrupted")
    ):
        with pytest.raises(HTTPException) as exc_info:
            await storage.download_archive(
                str(storage.root_dir),
                "test_download_archive_base_exception",
                background_tasks,
            )

        assert exc_info.value.status_code == 500
        assert "Failed to download archive" in exc_info.value.detail


@pytest.mark.anyio
async def test_copy_folder_source_not_found(storage: LocalStorage) -> None:
    """Test copying a non-existent source folder."""
    src_path = storage.root_dir / "nonexistent_folder"
    dst_path = storage.root_dir / "destination_folder"

    with pytest.raises(HTTPException) as exc_info:
        await storage.copy_folder(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Source folder not found"


@pytest.mark.anyio
async def test_get_file_from_url_unsupported_scheme(
    storage: LocalStorage,
) -> None:
    """Test get_file_from_url with unsupported URL scheme."""
    with pytest.raises(HTTPException) as exc_info:
        await storage.get_file_from_url("unsupported://example.com/file.txt")

    assert exc_info.value.status_code == 400
    assert "Unsupported URL scheme: unsupported" in exc_info.value.detail


@pytest.mark.anyio
async def test_copy_folder_destination_exists(storage: LocalStorage) -> None:
    """Test copying to an existing destination folder."""
    src_path = storage.root_dir / "source_folder"
    dst_path = storage.root_dir / "destination_folder"

    # Create both folders
    src_path.mkdir()
    dst_path.mkdir()
    (src_path / "file.txt").write_text("test")

    with pytest.raises(HTTPException) as exc_info:
        await storage.copy_folder(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Destination folder already exists"


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
async def test_move_file(storage: LocalStorage) -> None:
    """Test moving a file."""
    src_path = storage.root_dir / "test_move_file_src.json"
    dst_path = storage.root_dir / "test_move_file_dst.json"

    src_path.write_text('{"key": "value"}')

    await storage.move_file(str(src_path), str(dst_path))

    assert not src_path.exists()
    assert dst_path.exists()


@pytest.mark.anyio
async def test_copy_file(storage: LocalStorage) -> None:
    """Test copying a file."""
    src_path = storage.root_dir / "test_copy_file_src.json"
    dst_path = storage.root_dir / "test_copy_file_dst.json"

    src_path.write_text('{"key": "value"}')

    await storage.copy_file(str(src_path), str(dst_path))

    assert src_path.exists()
    assert dst_path.exists()


@pytest.mark.anyio
async def test_delete_file(storage: LocalStorage) -> None:
    """Test deleting a file."""
    file_path = storage.root_dir / "test_delete_file.json"
    file_path.write_text('{"key": "value"}')

    await storage.delete_file(str(file_path))

    assert not file_path.exists()


@pytest.mark.anyio
async def test_delete_folder(storage: LocalStorage) -> None:
    """Test deleting a folder."""
    folder = storage.root_dir / "test_delete_folder"
    folder.mkdir()
    (folder / "file.json").write_text('{"key": "value"}')

    await storage.delete_folder(str(folder))

    assert not folder.exists()


@pytest.mark.anyio
async def test_list_files(storage: LocalStorage) -> None:
    """Test listing files."""
    (storage.root_dir / "test_list_files_file1.json").write_text(
        '{"key": "value"}'
    )
    (storage.root_dir / "test_list_files_file2.json").write_text(
        '{"key": "value"}'
    )
    sub_folder = storage.root_dir / "test_list_files_sub_folder"
    sub_folder.mkdir()
    (sub_folder / "test_list_files_file3.json").write_text('{"key": "value"}')
    sub_sub_folder = sub_folder / "test_list_files_sub_sub_folder"
    sub_sub_folder.mkdir()
    (sub_sub_folder / "test_list_files_file4.json").write_text(
        '{"key": "value"}'
    )

    files = await storage.list_files(str(storage.root_dir))

    assert len(files) == 4


@pytest.mark.anyio
async def test_download_archive(storage: LocalStorage) -> None:
    """Test downloading an archive."""
    folder = storage.root_dir / "test_download_archive_folder"
    folder.mkdir()
    (folder / "test_download_archive_file1.json").write_text('{"key": "value"}')
    (folder / "test_download_archive_file2.json").write_text('{"key": "value"}')

    background_tasks = BackgroundTasks()

    response = await storage.download_archive(
        str(storage.root_dir), "test_download_archive_folder", background_tasks
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
) -> None:
    """Test saving a file with invalid MIME type."""
    # make a zip in storage.root_dir
    zip_path = storage.root_dir / "test_save_file_invalid_mime.zip"
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
async def test_move_file_failure(storage: LocalStorage) -> None:
    """Test moving a file."""
    src_path = storage.root_dir / "test_move_file_failure_src.json"
    dst_path = storage.root_dir / "test_move_file_failure_dst.json"

    src_path.write_text('{"key": "value"}')
    dst_path.write_text('{"key": "value"}')

    with pytest.raises(HTTPException) as exc_info:
        await storage.move_file(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Destination file already exists"


@pytest.mark.anyio
async def test_move_file_error(storage: LocalStorage) -> None:
    """Test moving a file."""
    src_path = storage.root_dir / "test_move_file_error_src.json"
    dst_path = storage.root_dir / "test_move_file_error_dst.json"

    src_path.write_text('{"key": "value"}')

    with patch("shutil.move", side_effect=OSError):
        with pytest.raises(HTTPException) as exc_info:
            await storage.move_file(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail.startswith("Failed to move file:")


@pytest.mark.anyio
async def test_copy_file_failure(storage: LocalStorage) -> None:
    """Test copying a file."""
    src_path = storage.root_dir / "test_copy_file_failure_src.json"
    dst_path = storage.root_dir / "test_copy_file_failure_dst.json"

    src_path.write_text('{"key": "value"}')
    dst_path.write_text('{"key": "value"}')

    with pytest.raises(HTTPException) as exc_info:
        await storage.copy_file(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Destination file already exists"


@pytest.mark.anyio
async def test_copy_file_src_not_found(storage: LocalStorage) -> None:
    """Test copying a file."""
    src_path = storage.root_dir / "test_copy_file_src_not_found_src.json"
    dst_path = storage.root_dir / "test_copy_file_src_not_found_dst.json"

    with pytest.raises(HTTPException) as exc_info:
        await storage.copy_file(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Source file not found"


@pytest.mark.anyio
async def test_copy_file_error(storage: LocalStorage) -> None:
    """Test copying a file."""
    src_path = storage.root_dir / "test_copy_file_error_src.json"
    dst_path = storage.root_dir / "test_copy_file_error_dst.json"

    src_path.write_text('{"key": "value"}')

    with patch("shutil.copyfile", side_effect=OSError):
        with pytest.raises(HTTPException) as exc_info:
            await storage.copy_file(str(src_path), str(dst_path))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail.startswith("Failed to copy file:")


@pytest.mark.anyio
async def test_download_archive_failure(storage: LocalStorage) -> None:
    """Test downloading an archive."""
    folder = storage.root_dir / "folder"
    folder.mkdir()
    (folder / "file1.json").write_text('{"key": "value"}')
    (folder / "file2.json").write_text('{"key": "value"}')

    background_tasks = BackgroundTasks()

    with patch("shutil.make_archive", side_effect=OSError):
        with pytest.raises(HTTPException) as exc_info:
            await storage.download_archive(
                str(storage.root_dir), "folder", background_tasks
            )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail.startswith("Failed to download archive")


@pytest.mark.anyio
async def test_download_archive_not_found(
    storage: LocalStorage,
) -> None:
    """Test downloading an archive."""
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as exc_info:
        await storage.download_archive(
            str(storage.root_dir), "folder", background_tasks
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to generate archive"


@pytest.mark.anyio
async def test_delete_file_not_found(
    storage: LocalStorage,
) -> None:
    """Test deleting a file."""
    file_path = storage.root_dir / "test_delete_file_not_found.json"
    assert not file_path.exists()
    await storage.delete_file(str(file_path))


@pytest.mark.anyio
async def test_delete_file_failure(
    storage: LocalStorage,
) -> None:
    """Test deleting a file."""
    file_path = storage.root_dir / "test_delete_file_failure.json"
    file_path.write_text('{"key": "value"}')

    with patch("aiofiles.os.unlink", side_effect=OSError):
        with pytest.raises(HTTPException) as exc_info:
            await storage.delete_file(str(file_path))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail.startswith("Failed to delete file")


@pytest.mark.anyio
async def test_delete_folder_not_found(
    storage: LocalStorage,
) -> None:
    """Test deleting a folder."""
    folder = storage.root_dir / "test_delete_folder_not_found"
    assert not folder.exists()
    await storage.delete_folder(str(folder))


@pytest.mark.anyio
async def test_delete_folder_failure(
    storage: LocalStorage,
) -> None:
    """Test deleting a folder."""
    folder = storage.root_dir / "test_delete_folder_failure"
    folder.mkdir()
    (folder / "file.json").write_text('{"key": "value"}')

    with patch("shutil.rmtree", side_effect=OSError):
        with pytest.raises(HTTPException) as exc_info:
            await storage.delete_folder(str(folder))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail.startswith("Failed to delete folder")


@pytest.mark.anyio
async def test_list_files_not_found(
    storage: LocalStorage,
) -> None:
    """Test listing files."""
    folder = storage.root_dir / "test_list_files_not_found"
    assert not folder.exists()
    files = await storage.list_files(str(folder))
    assert not files


@pytest.mark.anyio
async def test_copy_folder_success(storage: LocalStorage) -> None:
    """Test successful folder copying."""
    src_path = storage.root_dir / "source_folder"
    dst_path = storage.root_dir / "destination_folder"

    # Create source folder with content
    src_path.mkdir()
    (src_path / "file1.txt").write_text("content1")
    (src_path / "subdir").mkdir()
    (src_path / "subdir" / "file2.txt").write_text("content2")

    await storage.copy_folder(str(src_path), str(dst_path))

    # Verify copy was successful
    assert dst_path.exists()
    assert (dst_path / "file1.txt").exists()
    assert (dst_path / "subdir" / "file2.txt").exists()
    assert (dst_path / "file1.txt").read_text() == "content1"
    assert (dst_path / "subdir" / "file2.txt").read_text() == "content2"


@pytest.mark.anyio
async def test_copy_folder_error(storage: LocalStorage) -> None:
    """Test copy_folder with copytree error."""
    src_path = storage.root_dir / "source_folder"
    dst_path = storage.root_dir / "destination_folder"

    src_path.mkdir()
    (src_path / "file.txt").write_text("test")

    with patch("shutil.copytree", side_effect=OSError("Copy failed")):
        with pytest.raises(HTTPException) as exc_info:
            await storage.copy_folder(str(src_path), str(dst_path))

        assert exc_info.value.status_code == 500
        assert "Failed to copy folder" in exc_info.value.detail


@pytest.mark.anyio
async def test_list_files_max_depth_reached(storage: LocalStorage) -> None:
    """Test list_files with deep nesting that hits max_depth."""
    # Create deeply nested structure
    current_path = storage.root_dir / "level0"
    current_path.mkdir()

    # Create nested folders beyond max_depth (10)
    for i in range(12):
        current_path = current_path / f"level{i + 1}"
        current_path.mkdir()
        (current_path / f"file{i}.txt").write_text(f"content{i}")

    files = await storage.list_files(str(storage.root_dir))

    assert len(files) > 0


@pytest.mark.anyio
async def test_list_files_with_relative_path(storage: LocalStorage) -> None:
    """Test list_files with relative path."""
    # Create test structure
    test_folder = storage.root_dir / "test_list_files_with_relative_path"
    test_folder.mkdir()
    (test_folder / "file1.txt").write_text("content1")
    (test_folder / "file2.txt").write_text("content2")

    # Use relative path
    files = await storage.list_files("test_list_files_with_relative_path")
    assert len(files) == 2
    assert "file1.txt" in files
    assert "file2.txt" in files


@pytest.mark.anyio
async def test_copy_file_create_parent_dirs(storage: LocalStorage) -> None:
    """Test that copy_file creates parent directories."""
    src_path = storage.root_dir / "source.txt"
    dst_path = storage.root_dir / "nested" / "deep" / "destination.txt"

    src_path.write_text("test content")

    # Destination parent directories don't exist
    assert not dst_path.parent.exists()

    await storage.copy_file(str(src_path), str(dst_path))

    # Should create parent directories and copy file
    assert dst_path.exists()
    assert dst_path.read_text() == "test content"


@pytest.mark.anyio
async def test_move_file_create_parent_dirs(storage: LocalStorage) -> None:
    """Test that move_file creates parent directories."""
    src_path = storage.root_dir / "source.txt"
    dst_path = storage.root_dir / "nested" / "deep" / "destination.txt"

    src_path.write_text("test content")

    # Destination parent directories don't exist
    assert not dst_path.parent.exists()

    await storage.move_file(str(src_path), str(dst_path))

    # Should create parent directories and move file
    assert dst_path.exists()
    assert not src_path.exists()
    assert dst_path.read_text() == "test content"


@pytest.mark.anyio
async def test_download_archive_cleanup_called(
    storage: LocalStorage, tmp_path: Path
) -> None:
    """Test that download_archive cleanup function is properly called."""
    folder = storage.root_dir / "test_download_archive_cleanup_called"
    folder.mkdir()
    (folder / "file.txt").write_text("test")

    background_tasks = BackgroundTasks()

    # Mock the cleanup to verify it gets called
    with patch(
        "tempfile.mkdtemp", return_value=str(tmp_path / "test_temp_dir")
    ):
        with patch(
            "shutil.make_archive",
            return_value=str(tmp_path / "test_temp_dir" / "archive.zip"),
        ):
            response = await storage.download_archive(
                str(storage.root_dir),
                "test_download_archive_cleanup_called",
                background_tasks,
            )

            # Verify background task was added
            assert len(background_tasks.tasks) == 1
            assert response.status_code == 200
