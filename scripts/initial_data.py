# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""Initial data for the database."""

import json
import logging
import os
import sys
from pathlib import Path
from typing import List

from alembic import command
from alembic import config as alembic_config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

os.environ["PYTHONUNBUFFERED"] = "1"

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

ROOT_DIR = Path(__file__).parent.parent.resolve()
ALEMBIC_INI_PATH = ROOT_DIR / "alembic.ini"
DOT_ENV_PATH = ROOT_DIR / ".env"
INITIAL_CLIENTS_JSON = ROOT_DIR / "clients.json"  # must be .gitignored !!
LOG = logging.getLogger(__name__)

try:
    from waldiez_runner.config import SettingsManager
    from waldiez_runner.dependencies import CLIENT_API_AUDIENCE, VALID_AUDIENCES
    from waldiez_runner.models import Client, ClientCreate, ClientCreateResponse
except ImportError:
    sys.path.append(str(ROOT_DIR))
    from waldiez_runner.config import SettingsManager
    from waldiez_runner.dependencies import CLIENT_API_AUDIENCE, VALID_AUDIENCES
    from waldiez_runner.models import Client, ClientCreate, ClientCreateResponse


OTHER_AUDIENCES = [
    audience for audience in VALID_AUDIENCES if audience != CLIENT_API_AUDIENCE
]


def get_current_db_revision(alembic_cfg: alembic_config.Config) -> str | None:
    """Get the current revision from the database.

    Parameters
    ----------
    alembic_cfg : alembic_config.Config
        The Alembic configuration.

    Returns
    -------
    str
        The current revision in the database.

    Raises
    ------
    RuntimeError
        If no database URL is found in the Alembic configuration
    """
    sync_url = alembic_cfg.get_main_option("sqlalchemy.url")
    if not sync_url:
        raise RuntimeError("No database URL found in Alembic configuration")
    sync_engine = create_engine(sync_url, echo=True)
    with sync_engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        current_revision = migration_context.get_current_revision()
    sync_engine.dispose()
    return current_revision


def get_latest_revision(alembic_cfg: alembic_config.Config) -> str | None:
    """Get the latest revision from the Alembic versions.

    Parameters
    ----------
    alembic_cfg : alembic_config.Config
        The Alembic configuration.

    Returns
    -------
    str
        The latest revision in the Alembic versions.
    """
    script = ScriptDirectory.from_config(alembic_cfg)
    latest_revision = script.get_current_head()
    return latest_revision


def run_migrations() -> None:
    """Run the migrations."""
    alembic_cfg = alembic_config.Config(ALEMBIC_INI_PATH)
    settings = SettingsManager.load_settings(force_reload=False)
    database_url = settings.get_sync_database_url()
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    current_db_revision = get_current_db_revision(alembic_cfg)
    latest_revision = get_latest_revision(alembic_cfg)
    if current_db_revision is None:
        LOG.info("No current revision detected, applying all migrations...")
        command.upgrade(alembic_cfg, "head")
    elif current_db_revision != latest_revision:
        LOG.info(
            "Current revision is %s but latest is %s, applying migrations...",
            current_db_revision,
            latest_revision,
        )
        command.upgrade(alembic_cfg, "head")
    else:
        LOG.info("Database is up-to-date, no migrations needed.")


def check_first_client() -> None:
    """Ensure the first client exists in the database.

    Raises
    ------
    RuntimeError
        If the client ID or secret are not set in the environment.
    """
    settings = SettingsManager.load_settings(force_reload=False)
    client_id = settings.local_client_id
    client_secret = settings.local_client_secret
    if not client_id or not client_secret:
        raise RuntimeError("Local client ID and secret are required")
    database_url = settings.get_sync_database_url()
    sync_engine = create_engine(database_url, echo=True)
    with Session(sync_engine) as session:
        client = session.query(Client).filter_by(client_id=client_id).first()
        if client:
            LOG.info("Client %s already exists, skipping creation", client_id)
            # lat's also add it to the clients.json file
            update_clients_json(
                [
                    ClientCreateResponse.from_client(
                        client, client_secret.get_secret_value()
                    )
                ]
            )
            return
        client_create = ClientCreate(
            client_id=client_id,
            plain_secret=client_secret.get_secret_value(),
            name="Default clients-api client",
            audience="clients-api",
            description="Default client to handle other clients using the API",
        )
        client = Client(
            client_id=client_create.client_id,
            client_secret=client_create.hashed_secret(),
            audience=client_create.audience,
            name=client_create.name,
            description=client_create.description,
        )
        session.add(client)
        session.commit()
        LOG.info("Client created")
        update_clients_json(
            [
                ClientCreateResponse.from_client(
                    client, client_secret.get_secret_value()
                )
            ]
        )


def update_clients_json(new_clients: List[ClientCreateResponse]) -> None:
    """Update the clients.json file with new clients.

    Parameters
    ----------
    new_clients : list[ClientCreateResponse]
        The new clients to add to the JSON file.
    """
    clients = []
    if INITIAL_CLIENTS_JSON.exists():
        with INITIAL_CLIENTS_JSON.open("r", encoding="utf-8") as json_file:
            clients = json.load(json_file)
    for client in new_clients:
        clients.append(
            {
                "id": client.id,
                "client_id": client.client_id,
                "client_secret": client.client_secret,
                "audience": client.audience,
                "name": client.name,
                "description": client.description,
            }
        )
    with INITIAL_CLIENTS_JSON.open(
        "w", encoding="utf-8", newline="\n"
    ) as json_file:
        json.dump(clients, json_file, indent=4)
    LOG.info("clients.json updated")


def ensure_clients_api_client() -> None:
    """Make sure at least one client with clients-api audience exists in db."""
    settings = SettingsManager.load_settings(force_reload=False)
    sync_engine = create_engine(settings.get_sync_database_url(), echo=True)
    with Session(sync_engine) as session:
        client = session.query(Client).filter_by(audience="clients-api").first()
        if client:
            LOG.info(
                "A Client for clients-api already exists, skipping creation"
            )
            return
    check_first_client()


def ensure_other_clients() -> None:
    """Ensure other clients (per audience) exist in the database."""
    # two audiences (for now?): clients-api and tasks-api
    # for the clients-api we check above
    # let's check if one for tasks-api exists and create it if not
    new_clients: list[ClientCreateResponse] = []
    settings = SettingsManager.load_settings(force_reload=False)
    database_url = settings.get_sync_database_url()
    sync_engine = create_engine(database_url, echo=True)
    with Session(sync_engine) as session:
        for audience in OTHER_AUDIENCES:
            client = session.query(Client).filter_by(audience=audience).first()
            if client:
                LOG.info(
                    "Client for %s already exists, skipping creation", audience
                )
                continue
            name = audience.split("-")[0].capitalize()
            client_create = ClientCreate(
                audience=audience,
                name=f"{name} client",
                description=f"{name} management API",
            )
            client = Client(
                client_id=client_create.client_id,
                client_secret=client_create.hashed_secret(),
                audience=client_create.audience,
                name=client_create.name,
                description=client_create.description,
            )
            session.add(client)
            session.commit()
            new_clients.append(
                ClientCreateResponse.from_client(
                    client, client_create.plain_secret
                )
            )

    if new_clients:
        LOG.info(
            "Clients created for %s",
            ", ".join(audience for audience in OTHER_AUDIENCES),
        )
        update_clients_json(new_clients)


def main() -> None:
    """Perform initial data setup."""
    use_postgres: bool | None = None
    if "--no-postgres" in sys.argv:
        use_postgres = False
    if "--postgres" in sys.argv:
        use_postgres = True
    if use_postgres is not None:
        settings = SettingsManager.load_settings(force_reload=True)
        LOG.info("Settings: \n%s", settings.model_dump_json(indent=2))
        settings.postgres = use_postgres
        settings.save()
        LOG.info("Postgres enabled: %s", use_postgres)
    testing = os.environ.get("WALDIEZ_RUNNER_TESTING", "false").lower() in (
        "true",
        "yes",
        "1",
    )
    if "--dev" in sys.argv:
        testing = False
    if not testing:
        run_migrations()
        ensure_clients_api_client()
        ensure_other_clients()
        LOG.info("Bootstrap completed")


if __name__ == "__main__":
    main()
