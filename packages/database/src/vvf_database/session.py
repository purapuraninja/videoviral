"""Engine and session helpers for VVF."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_dsn(
    host: str | None = None,
    port: str | int | None = None,
    db: str | None = None,
    user: str | None = None,
    password: str | None = None,
) -> str:
    """Build a PostgreSQL DSN from individual env-style values."""
    host = host or os.getenv("POSTGRES_HOST", "localhost")
    port = str(port or os.getenv("POSTGRES_PORT", "5432"))
    db = db or os.getenv("POSTGRES_DB", "vvf")
    user = user or os.getenv("POSTGRES_USER", "vvf")
    password = password or os.getenv("POSTGRES_PASSWORD", "")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def build_engine(dsn: str | None = None, **kwargs: Any) -> Engine:
    """Create a SQLAlchemy engine from a DSN (or env vars)."""
    url = dsn or make_dsn()
    defaults: dict[str, Any] = {"pool_pre_ping": True, "future": True}
    defaults.update(kwargs)
    return create_engine(url, **defaults)


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    engine = engine or build_engine()
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def get_session(engine: Engine | None = None) -> Iterator[Session]:
    """FastAPI-style dependency yielding a session."""
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
