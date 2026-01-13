# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.


"""Checksum related utils."""

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Get the sha256sum of a file.

    Parameters
    ----------
    path : Path
        The path to get the sha256sum

    Returns
    -------
    str
        The calculated sha256sum.
    """
    h = hashlib.sha256(usedforsecurity=False)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_checksum(path: Path) -> Path:
    """Store the sha256sum to a file.

    Parameters
    ----------
    path : Path
        The path to get the sha256sum

    Returns
    -------
    Path
        The generated file.
    """
    digest = sha256_file(path)
    out = path.with_suffix(path.suffix + ".sha256")
    out.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return out


def verify_checksum(archive: Path) -> tuple[bool, str]:
    """Verify a sha256sum of an archive.

    Parameters
    ----------
    archive : Path
        The path of the archive to check.

    Returns
    -------
    tuple[bool, str]
        A tuple (is_valid, message) with the result.

    """
    check = archive.with_suffix(archive.suffix + ".sha256")
    if not check.exists():
        return False, "Checksum file not found"

    line = check.read_text(encoding="utf-8").strip()
    parts = line.split()
    if len(parts) < 2:
        return False, "Invalid checksum format"

    expected, filepart = parts[0], parts[-1]
    if Path(filepart).name != archive.name:
        return False, f"Filename mismatch: {filepart} != {archive.name}"

    actual = sha256_file(archive)
    if actual != expected:
        return False, f"Checksum mismatch: {actual} != {expected}"

    return True, "Valid"
