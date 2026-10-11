"""Database engine / session management (SQLAlchemy 2.x + SQLite)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _make_engine(url: str | None = None) -> Engine:
    settings = get_settings()
    resolved = url or settings.resolved_database_url
    connect_args: dict[str, object] = {}
    if resolved.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30

    created = create_engine(
        resolved,
        echo=False,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

    if resolved.startswith("sqlite"):

        @event.listens_for(created, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return created


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionFactory


def reset_engine(url: str | None = None) -> Engine:
    """Rebuild the process-wide engine (used by tests to point at a temp DB)."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = _make_engine(url)
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def init_db(url: str | None = None) -> Engine:
    engine = reset_engine(url) if url else get_engine()
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error, always close."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()