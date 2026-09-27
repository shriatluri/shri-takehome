"""Migration and seed runner.

Plain SQL files applied in filename order by the owner role, tracked in
``schema_migrations``. Files ending in ``.tmpl.sql`` are formatted with the
database identifiers from settings before they run, which is how the runtime
role name and password reach ``CREATE ROLE`` and ``GRANT`` without being
hardcoded in the SQL.
"""

import logging
from pathlib import Path

import psycopg
from psycopg import sql

from app.config import MIGRATIONS_DIR, SEED_DIR, Settings

logger = logging.getLogger(__name__)

_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def _render(path: Path, settings: Settings) -> sql.Composable:
    body = path.read_text()
    if not path.name.endswith(".tmpl.sql"):
        return sql.SQL(body)  # type: ignore[arg-type]
    return sql.SQL(body).format(  # type: ignore[arg-type]
        app_user=sql.Identifier(settings.app_user),
        app_user_name=sql.Literal(settings.app_user),
        app_password=sql.Literal(settings.app_password),
        database=sql.Identifier(settings.database),
    )


def _sql_files(directory: Path) -> list[Path]:
    files = sorted(directory.glob("*.sql")) if directory.is_dir() else []
    if not files:
        raise FileNotFoundError(f"no .sql files found in {directory}")
    return files


def run_migrations(settings: Settings, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply every unapplied migration. Returns the versions applied."""
    applied: list[str] = []
    with psycopg.connect(settings.owner_url) as conn:
        with conn.cursor() as cur:
            cur.execute(_TRACKING_TABLE)
            cur.execute("SELECT version FROM schema_migrations")
            done = {row[0] for row in cur.fetchall()}
        conn.commit()

        for path in _sql_files(migrations_dir):
            version = path.name
            if version in done:
                continue
            logger.info("applying migration %s", version)
            with conn.cursor() as cur:
                cur.execute(_render(path, settings))
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            conn.commit()
            applied.append(version)
    return applied


def database_is_seeded(settings: Settings) -> bool:
    with psycopg.connect(settings.owner_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM employees")
        return cur.fetchone()[0] > 0


def run_seed(settings: Settings, seed_dir: Path = SEED_DIR, force: bool = False) -> bool:
    """Load seed data. Skipped when the database already has employees.

    The seed files truncate before inserting, so ``force=True`` restores the
    original demo state. Only the test suite uses it; there is no reset route.
    """
    if not force and database_is_seeded(settings):
        return False
    with psycopg.connect(settings.owner_url) as conn:
        for path in _sql_files(seed_dir):
            logger.info("loading seed file %s", path.name)
            with conn.cursor() as cur:
                cur.execute(sql.SQL(path.read_text()))  # type: ignore[arg-type]
        conn.commit()
    return True
