# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2026 Waldiez and contributors.

"""Check for revision and generate it if needed."""

import logging
import os
import sys
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from dotenv import load_dotenv
from sqlalchemy import create_engine

os.environ["PYTHONUNBUFFERED"] = "1"

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

ROOT_DIR = Path(__file__).parent.parent.resolve()
DOT_ENV_PATH = ROOT_DIR / ".env"
ALEMBIC_INI_PATH = ROOT_DIR / "alembic.ini"
LOG = logging.getLogger(__name__)


if DOT_ENV_PATH.exists():
    load_dotenv(DOT_ENV_PATH, override=False)
try:
    from waldiez_runner.config import SettingsManager
    from waldiez_runner.models.common import Base
except ImportError:
    sys.path.append(str(ROOT_DIR))
    from waldiez_runner.config import SettingsManager
    from waldiez_runner.models.common import Base

SETTINGS = SettingsManager.load_settings()


def generate_revision(alembic_cfg: Config) -> None:
    """Generate a migration.

    Parameters
    ----------
    alembic_cfg : Config
        The Alembic configuration.
    """
    command.revision(alembic_cfg, autogenerate=True, message="Auto migrated")


def needs_revision() -> bool:
    """Check if the database needs revision.

    Returns
    -------
    bool
        Whether the database needs revision.
    """
    sync_url = SETTINGS.get_sync_database_url()
    sync_engine = create_engine(sync_url, echo=True)
    it_does = False
    with sync_engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        diff = compare_metadata(migration_context, Base.metadata)
        LOG.info("Migration diff: %s", diff)
        it_does = bool(diff)
    sync_engine.dispose()
    return it_does


def main() -> None:
    """Check if a revision is needed and generate one if needed."""
    if needs_revision():
        alembic_cfg = Config(ALEMBIC_INI_PATH)
        generate_revision(alembic_cfg=alembic_cfg)


if __name__ == "__main__":
    main()
