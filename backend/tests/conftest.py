import os
from dataclasses import replace

import psycopg
import pytest
from psycopg import sql

from app.config import Settings
from app.platform.migrations import run_migrations, run_seed

# The suite reseeds and the seed truncates, so running against the database
# behind `docker compose up` would wipe whatever the demo is partway through.
# Redirect everything imported afterwards — including the FastAPI app and its
# engine — at a throwaway database.
_ADMIN_DATABASE = Settings.from_env().database
os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME", f"{_ADMIN_DATABASE}_test")


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture(scope="session", autouse=True)
def migrated_database(settings: Settings) -> Settings:
    _create_database(settings)
    run_migrations(settings)
    run_seed(settings, force=True)
    return settings


def _create_database(settings: Settings) -> None:
    admin = replace(settings, database=_ADMIN_DATABASE)
    with psycopg.connect(admin.owner_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.database,))
        if cur.fetchone() is None:
            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.database))
            )


@pytest.fixture
def owner_conn(settings: Settings):
    with psycopg.connect(settings.owner_url) as conn:
        yield conn


@pytest.fixture
def app_conn(settings: Settings):
    """Connection as the runtime role, i.e. what the API itself can do."""
    with psycopg.connect(settings.url(settings.app_user, settings.app_password)) as conn:
        yield conn
