"""Drop, recreate, migrate and reseed the database.

This is the mid-presentation reset button: one command puts the demo back to a
known state.  It is deliberately safe to run repeatedly.

Run with:  python -m scripts.reset_db      (from the api/ directory)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url

from app.config import settings

API_DIR = Path(__file__).resolve().parents[1]


def maintenance_dsn() -> str:
    """A libpq DSN for the 'postgres' maintenance database on the same server.

    We cannot drop a database while connected to it, so the drop/create runs
    against 'postgres' using the same credentials.
    """
    url = make_url(settings.database_url)
    return psycopg.conninfo.make_conninfo(
        host=url.host or "localhost",
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname="postgres",
    )


def recreate_database() -> None:
    url = make_url(settings.database_url)
    db_name = url.database or settings.db_name

    with psycopg.connect(maintenance_dsn(), autocommit=True) as conn:
        # WITH (FORCE) terminates leftover connections - a stray API process
        # otherwise blocks the drop. Requires PostgreSQL 13 or newer.
        conn.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
        print(f"dropped database {db_name}")
        conn.execute(f'CREATE DATABASE "{db_name}"')
        print(f"created database {db_name}")


def run(command: list[str], step: str) -> None:
    print(f"\n=== {step} ===")
    result = subprocess.run(command, cwd=API_DIR)
    if result.returncode != 0:
        sys.exit(f"{step} failed with exit code {result.returncode}")


def main() -> None:
    recreate_database()
    run([sys.executable, "-m", "alembic", "upgrade", "head"], "alembic upgrade head")
    run([sys.executable, "-m", "scripts.seed"], "seed")
    print("\nDatabase reset complete.")


if __name__ == "__main__":
    main()
