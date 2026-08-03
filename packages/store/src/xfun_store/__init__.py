"""Persistence for canonical entities and the append-only score store.

Used by ingestion (writes entities), the scoring runner (writes scores), and the
API (reads both). It belongs to none of them, which is why it is its own package.
"""

from .availability import (
    MatchAvailability,
    read_availability,
    read_availability_map,
    write_availability,
)
from .collection import (
    PathProvenance,
    explain_missing_path,
    latest_run,
    read_run,
    write_collection_run,
)
from .db import DB_PATH, applied_migrations, connect, migrate
from .entities import load_snapshots, match_leagues, write_snapshot_payload
from .schedule_run import ScheduleRun, latest_schedule_run, write_schedule_run
from .scores import all_scores, latest_scores, register_models, write_scores

__all__ = [
    "DB_PATH",
    "MatchAvailability",
    "PathProvenance",
    "ScheduleRun",
    "all_scores",
    "applied_migrations",
    "connect",
    "explain_missing_path",
    "latest_run",
    "latest_schedule_run",
    "latest_scores",
    "load_snapshots",
    "match_leagues",
    "migrate",
    "read_availability",
    "read_availability_map",
    "read_run",
    "register_models",
    "write_availability",
    "write_collection_run",
    "write_schedule_run",
    "write_scores",
    "write_snapshot_payload",
]
