"""Running an adapter into the store."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from xfun_store import write_snapshot_payload

from .adapter import SourceAdapter

__all__ = ["IngestResult", "ingest"]


@dataclass
class IngestResult:
    source_id: str
    matches: int = 0

    def summary(self) -> str:
        return f"{self.source_id}: {self.matches} matches"


def ingest(conn: sqlite3.Connection, adapter: SourceAdapter) -> IngestResult:
    """Write everything an adapter yields into canonical entities.

    Idempotent: entity writes are upserts keyed on natural identifiers, so running
    this repeatedly converges rather than duplicating.
    """
    result = IngestResult(source_id=adapter.source_id)
    for payload in adapter.fetch():
        write_snapshot_payload(conn, payload)
        result.matches += 1
    return result
