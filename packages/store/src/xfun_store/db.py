"""Connection handling and migrations.

SQLite, stored at `.data/xfun.db`. Chosen so the end-to-end demo runs with no
daemon, no container, and no credentials -- which matters when the point of this
repository is that a collaborator can clone it and see it work.

Migrations are plain .sql files applied in filename order. No framework: at this
size one would be more machinery than the problem deserves.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator

from xfun_runtime.paths import data_dir, repo_root

__all__ = ["connect", "migrate", "applied_migrations", "DB_PATH"]

DB_PATH = "xfun.db"


def _migrations_dir() -> Path:
    return repo_root() / "infra" / "migrations"


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open a connection with foreign keys on and rows as mappings."""
    target = Path(path) if path is not None else data_dir() / DB_PATH
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def applied_migrations(conn: sqlite3.Connection) -> set[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migration ("
        " filename TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    return {row["filename"] for row in conn.execute("SELECT filename FROM schema_migration")}


def migrate(conn: sqlite3.Connection) -> Iterator[str]:
    """Apply pending migrations in filename order. Yields each one applied."""
    already = applied_migrations(conn)

    for path in sorted(_migrations_dir().glob("*.sql")):
        if path.name in already:
            continue
        conn.executescript(path.read_text())
        conn.execute("INSERT INTO schema_migration (filename) VALUES (?)", (path.name,))
        conn.commit()
        yield path.name
