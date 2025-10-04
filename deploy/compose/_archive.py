#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

# pylint: disable=broad-exception-caught,inconsistent-quotes
# pylint: disable=missing-function-docstring,missing-param-doc
# pylint: disable=missing-return-doc,missing-yield-doc,missing-raises-doc
# pyright: reportConstantRedefinition=false

"""Archive related functions."""

import logging
import os
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path


def make_archive(
    src_root: Path,
    out_path: Path,
    tar_root: str,
    mtime_iso: str,
) -> None:
    """Create a gzipped tar with normalized root folder name and mtime."""
    # Tarfile doesn't let us set mtime globally; we set per member.
    dt = datetime.strptime(mtime_iso, "%Y%m%dT%H%M%SZ")
    epoch = int(dt.replace(tzinfo=timezone.utc).timestamp())

    def _add(tar: tarfile.TarFile, path: Path, archive_name: str) -> None:
        info = tar.gettarinfo(str(path), archive_name)
        info.uid = 0
        info.gid = 0
        info.uname = "root"
        # cspell: disable-next-line
        info.gname = "root"
        info.mtime = epoch
        if path.is_file():
            with path.open("rb") as file:
                tar.addfile(info, file)
        else:
            tar.addfile(info)

    with tarfile.open(out_path, mode="w:gz", compresslevel=6) as tf:
        # add everything under src_root but prefix with tar_root/
        _add(tf, src_root, tar_root)
        for path in sorted(src_root.rglob("*")):
            rel = path.relative_to(src_root)
            _add(tf, path, str(Path(tar_root) / rel))


def extract_archive(
    archive: Path,
    dest: Path,
    *,
    allow_links: bool = False,
) -> Path:
    """Extract a tar.* archive into `dest`."""
    dest.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive, mode="r:*") as tar:
        members = tar.getmembers()
        # Identify a single top-level root (if any)
        roots: set[str] = set()
        for member in members:
            name = member.name.lstrip("./")
            if not name:
                continue
            roots.add(name.split("/", 1)[0])
        extracted_root = dest / (roots.pop() if len(roots) == 1 else "")
        _handle_tar_members(
            tar=tar, members=members, dest=dest, allow_links=allow_links
        )

    return extracted_root if extracted_root != dest else dest


def _is_within(p: Path, resolved: Path) -> bool:
    try:
        return p.resolve().is_relative_to(resolved)  # py>=3.9
    except AttributeError:
        # Fallback for older Pythons
        return (
            str(p.resolve()).startswith(str(resolved) + os.sep)
            or p.resolve() == resolved
        )


def _restore_target_meta(member: tarfile.TarInfo, target: Path) -> None:
    try:
        os.chmod(target, member.mode)
    except Exception:
        pass
    try:
        os.utime(target, (member.mtime, member.mtime))
    except Exception:
        pass


def _handle_member_link(
    member: tarfile.TarInfo, target: Path, dest: Path, dest_resolved: Path
) -> None:
    # Create symlink/hardlink carefully if allowed
    if member.issym():
        # symlink target is m.linkname (as-is)
        link_target = Path(target.parent / member.linkname).resolve()
        if not _is_within(link_target, dest_resolved):
            raise ValueError(
                f"Symlink target escapes dest: {member.linkname!r}"
            )
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(member.linkname, target)
        except (OSError, FileExistsError) as e:
            logging.debug("Failed to create symlink %s: %s", target, e)
    else:
        # hardlink: link to another extracted path
        link_src = (dest / member.linkname).resolve()
        if not _is_within(link_src, dest_resolved):
            raise ValueError(f"Hardlink escapes dest: {member.linkname!r}")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(link_src, target)
        except FileExistsError:
            pass
    # set metadata best-effort
    _restore_target_meta(member, target)


def _handle_tar_members(
    tar: tarfile.TarFile,
    members: list[tarfile.TarInfo],
    dest: Path,
    allow_links: bool,
) -> None:
    resolved_dst = dest.resolve()

    for member in members:
        # Normalize/sanitize name
        name = member.name.lstrip("/")  # no absolute
        name = name.replace("\\", "/")  # normalize
        # reject parent traversal
        parts = [p for p in name.split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts):
            raise ValueError(f"Unsafe path in archive: {member.name!r}")

        target = dest / "/".join(parts)
        if not _is_within(target, resolved_dst):
            raise ValueError(f"Extraction would escape dest: {member.name!r}")

        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            # best-effort mtime
            try:
                os.utime(target, (member.mtime, member.mtime))
            except Exception:
                pass
            continue

        if member.issym() or member.islnk():
            if not allow_links:
                # Skip links unless explicitly allowed (safer default)
                continue
            _handle_member_link(member, target, dest, resolved_dst)
            continue

        # Regular file
        f_src = tar.extractfile(member)
        if f_src is None:
            # Could be special file; skip
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with f_src, open(target, "wb") as f_dst:
            shutil.copyfileobj(f_src, f_dst)

        # best-effort perms + mtime
        _restore_target_meta(member, target)
