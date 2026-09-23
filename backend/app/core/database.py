"""
Database engine, session factory and the declarative base.

Two things worth stating explicitly, because they are migration-safety
properties rather than style choices:

1. **The models map onto the existing schema; they never create it.**
   `Base.metadata.create_all()` is deliberately not called anywhere. The
   database is owned by `database/schema.sql` and populated by
   `database/seed.sql`. Any future change goes through Alembic with the
   current schema as the baseline revision.

2. **`expire_on_commit=False`.** Response models are built from ORM objects
   after the request's transaction commits. With the SQLAlchemy default those
   attributes would expire and trigger a lazy reload against a closed session,
   which surfaces as `DetachedInstanceError` at serialisation time.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,   # a pooled connection can die while the app idles
    pool_size=5,
    max_overflow=10,
    echo=settings.db_echo,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


class Base(DeclarativeBase):
    """Declarative base for every mapped class in :mod:`app.models`."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> bool:
    """Cheap liveness probe used by `/health` and the startup log line."""
    from sqlalchemy import text

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - the caller only needs the boolean
        return False
