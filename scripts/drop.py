# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Drop the tables and types in the database."""

import os
import shutil
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).parent.parent.resolve()
STORAGE_DIR = ROOT_DIR / "waldiez_runner" / "storage"
INITIAL_CLIENTS_JSON = ROOT_DIR / "clients.json"  # must be .gitignored !!
os.environ["PYTHONUNBUFFERED"] = "1"

try:
    from waldiez_runner.config import SettingsManager
except ImportError:
    sys.path.append(str(ROOT_DIR))
    from waldiez_runner.config import SettingsManager


DROP_STATEMENTS = [
    "DROP TABLE IF EXISTS alembic_version",
    "DROP TABLE IF EXISTS tasks",
    "DROP TABLE IF EXISTS clients",
    "DROP TYPE IF EXISTS task_status",
]


def delete_storage() -> None:
    """Delete the storage directory."""
    if STORAGE_DIR.exists():
        for item in STORAGE_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                os.remove(item)
    else:
        print(f"Storage directory does not exist: {STORAGE_DIR}")
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    """Drop the tables."""
    settings = SettingsManager.load_settings(force_reload=False)
    db_sync_url = settings.get_sync_database_url()
    print(f"Using database URL: {db_sync_url}")
    sync_engine = create_engine(db_sync_url, echo=True)
    dialect = sync_engine.dialect.name
    with Session(sync_engine) as session:
        for statement in DROP_STATEMENTS:
            if dialect == "sqlite" and "DROP TYPE" in statement:
                continue
            print(f"Executing: {statement}")
            session.execute(text(statement))
        session.commit()
    with open(INITIAL_CLIENTS_JSON, "w", encoding="utf-8") as f:
        f.write("[]")
    print("Tables and types dropped.")
    print("The clients.json file has been reset.")
    print("The database is now empty.")
    delete_storage()


if __name__ == "__main__":
    if "--force" not in sys.argv:
        print("WARNING: All data in the database and storage will be deleted.")
        print("Press Ctrl+C to cancel in the next 10 seconds.")
        time.sleep(10)
    main()
