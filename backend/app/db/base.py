"""SQLAlchemy engine/session wiring. One scoped session per request (or per RQ
job, from Phase 3), removed in a teardown hook so connections go back to the pool.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, scoped_session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_session_factory: scoped_session[Session] | None = None


def init_engine(database_url: str) -> Engine:
    global _engine, _session_factory
    _engine = create_engine(database_url, pool_pre_ping=True, future=True)
    _session_factory = scoped_session(
        sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    )
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database engine not initialized — call init_engine() first.")
    return _engine


def get_session() -> Session:
    if _session_factory is None:
        raise RuntimeError("Database engine not initialized — call init_engine() first.")
    return _session_factory()


def remove_session() -> None:
    if _session_factory is not None:
        _session_factory.remove()
