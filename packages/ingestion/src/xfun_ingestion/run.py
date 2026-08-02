"""Writing canonical entities into the store."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from xfun_store import write_snapshot_payload

__all__ = ["IngestResult", "ingest"]


@dataclass
class IngestResult:
    source_id: str
    matches: int = 0

    def summary(self) -> str:
        return f"{self.source_id}: {self.matches} matches"


def ingest(
    conn: sqlite3.Connection,
    payloads: Iterable[Mapping[str, Any]],
    *,
    source_id: str = "fixture-file",
) -> IngestResult:
    """Write everything the source yields into canonical entities.

    Takes payloads rather than an adapter object. The `SourceAdapter` protocol this
    replaced existed to let several sources be plugged in, but that job now belongs
    to collectors -- which fan out from a slate and key their output by entity,
    rather than each yielding whole match payloads with no way to share a fetch.

    What remains here is narrower and concrete: turn match payloads into canonical
    rows. Idempotent, because entity writes are upserts on natural identifiers, so
    running this repeatedly converges rather than duplicating.
    """
    result = IngestResult(source_id=source_id)
    for payload in payloads:
        write_snapshot_payload(conn, payload)
        result.matches += 1
    return result
