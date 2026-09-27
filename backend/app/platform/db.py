"""Database access for request handling.

Everything here connects as the non-owner app role, so row-level security (added
with the policies in PR 2) applies to every query the API makes.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings

_settings = Settings.from_env()

engine = create_engine(_settings.app_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a transaction-scoped session.

    PR 2 sets ``app.user_id`` on this session with ``SET LOCAL`` so the caller's
    identity is visible to RLS policies and to the audit logger.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
