"""Database access for request handling.

Everything here connects as the non-owner app role, so the row-level security
policies in ``004_rls.sql`` apply to every query the API makes.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings

_settings = Settings.from_env()

engine = create_engine(_settings.app_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


@contextmanager
def session_scope(user_id: int | None) -> Iterator[Session]:
    """A transaction with ``app.user_id`` set to the caller, if there is one.

    ``SET LOCAL`` (``set_config(..., true)``) scopes the setting to this
    transaction, so a pooled connection cannot hand one request's identity to
    the next. Without it the setting is absent and the policies match no rows,
    which is the behaviour we want for an unauthenticated connection.
    """
    session = SessionLocal()
    try:
        if user_id is not None:
            session.execute(
                text("SELECT set_config('app.user_id', :user_id, true)"),
                {"user_id": str(user_id)},
            )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def session_for(user_id: int | None) -> Iterator[Session]:
    with session_scope(user_id) as session:
        yield session


def anonymous_session() -> Iterator[Session]:
    """FastAPI dependency for routes that run before anyone is signed in."""
    yield from session_for(None)
