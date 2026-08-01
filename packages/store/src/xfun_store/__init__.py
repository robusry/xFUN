"""Persistence for canonical entities and the append-only score store.

Used by ingestion (writes entities), the scoring runner (writes scores), and the
API (reads both). It belongs to none of them, which is why it is its own package.
"""

from .db import DB_PATH, applied_migrations, connect, migrate
from .entities import load_snapshots, match_leagues, write_snapshot_payload
from .scores import all_scores, latest_scores, register_models, write_scores

__all__ = [
    "DB_PATH",
    "all_scores",
    "applied_migrations",
    "connect",
    "latest_scores",
    "load_snapshots",
    "match_leagues",
    "migrate",
    "register_models",
    "write_scores",
    "write_snapshot_payload",
]
