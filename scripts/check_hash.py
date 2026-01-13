# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

"""Check and update the SHA256 hash in the do.sh script."""

import argparse
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).parent
SCRIPT_PATH = HERE.parent / "deploy" / "compose" / "do.sh"
HASH_COMMENT_PREFIX = "# SHA256:"


def compute_hash(path: Path) -> str:
    """Compute the SHA256 hash of the file, ignoring the hash line.

    Parameters
    ----------
    path : Path
        Path to the file.

    Returns
    -------
    str
        SHA256 hash of the file.
    """
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        for line in f:
            if line.startswith(b"# SHA256:"):
                continue
            sha256.update(line)
    return sha256.hexdigest()


def extract_existing_hash(path: Path) -> str | None:
    """Extract the existing SHA256 hash from the file.

    Parameters
    ----------
    path : Path
        Path to the file.

    Returns
    -------
    str | None
        Existing SHA256 hash if found, None otherwise.
    """
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(HASH_COMMENT_PREFIX):
            return line[len(HASH_COMMENT_PREFIX) :].strip()
    return None


def update_hash_line(path: Path, new_hash: str) -> bool:
    """Update the SHA256 hash line in the file.

    Parameters
    ----------
    path : Path
        Path to the file.
    new_hash : str
        New SHA256 hash to write.

    Returns
    -------
    bool
        True if the file was modified, False otherwise.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(HASH_COMMENT_PREFIX):
            if line.strip() != f"{HASH_COMMENT_PREFIX} {new_hash}":
                lines[i] = f"{HASH_COMMENT_PREFIX} {new_hash}"
                updated = True
            break
    else:
        # No hash line found, insert after shebang or at top
        starting_indicator = "#!"
        insert_at = (
            1 if lines and lines[0].startswith(starting_indicator) else 0
        )
        lines.insert(insert_at, f"{HASH_COMMENT_PREFIX} {new_hash}")
        updated = True

    if updated:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated


def check_hash(path: Path, expected_hash: str) -> bool:
    """Check if the SHA256 hash in the file matches the expected hash.

    Parameters
    ----------
    path : Path
        Path to the file.
    expected_hash : str
        Expected SHA256 hash.

    Returns
    -------
    bool
        True if the hash matches, False otherwise.
    """
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(HASH_COMMENT_PREFIX):
            current = line.strip().split(":", 1)[1].strip()
            return current == expected_hash
    return False


def main() -> None:
    """Main function to compute and update the SHA256 hash in the script."""
    if not SCRIPT_PATH.exists():
        print(f"Script not found at {SCRIPT_PATH}")
        sys.exit(1)
    parser = argparse.ArgumentParser(
        description="Update or check SHA256 hash in do.sh"
    )
    parser.add_argument(
        "--check", action="store_true", help="Only check the hash, don't modify"
    )
    args = parser.parse_args()
    new_hash = compute_hash(SCRIPT_PATH)
    existing_hash = extract_existing_hash(SCRIPT_PATH)
    if args.check:
        if existing_hash != new_hash:
            print(f"SHA256 mismatch in {SCRIPT_PATH}!")
            print(f"Expected: {new_hash}")
            sys.exit(1)
        print("SHA256 is correct.")
    else:
        changed = update_hash_line(SCRIPT_PATH, new_hash)
        if changed:
            print(f"Updated SHA256 hash in {SCRIPT_PATH} to: {new_hash}")
        else:
            print("SHA256 already up to date.")


if __name__ == "__main__":
    main()
