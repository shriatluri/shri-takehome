import psycopg
import pytest

from app.config import Settings
from app.platform.migrations import run_migrations, run_seed


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture(scope="session", autouse=True)
def migrated_database(settings: Settings) -> Settings:
    run_migrations(settings)
    run_seed(settings, force=True)
    return settings


@pytest.fixture
def owner_conn(settings: Settings):
    with psycopg.connect(settings.owner_url) as conn:
        yield conn


@pytest.fixture
def app_conn(settings: Settings):
    """Connection as the runtime role, i.e. what the API itself can do."""
    with psycopg.connect(settings.url(settings.app_user, settings.app_password)) as conn:
        yield conn
