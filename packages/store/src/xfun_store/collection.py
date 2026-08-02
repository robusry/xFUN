"""Persisting and reading the collection run record.

The write side is unremarkable. The read side exists for one question, asked by an
operator staring at a match with no score: **why?**

Answering it needs three facts the score store cannot supply -- whether the
collector that should have produced the data was invoked at all, whether it
succeeded, and whether it returned anything for this particular match. Those live
here.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "PathProvenance",
    "explain_missing_path",
    "latest_run",
    "read_run",
    "write_collection_run",
]


def write_collection_run(
    conn: sqlite3.Connection,
    run: Any,
    selection: Mapping[str, Any],
) -> None:
    """Record one collection run.

    Takes the runtime's `CollectionRun` structurally rather than importing it, so
    the store keeps depending on nothing above it.
    """
    conn.execute(
        "INSERT OR REPLACE INTO collection_run "
        "(run_id, slate_id, selection, started_at, completed_at) VALUES (?, ?, ?, ?, ?)",
        (
            run.run_id,
            run.slate_id,
            json.dumps(dict(selection), sort_keys=True),
            run.started_at,
            run.completed_at,
        ),
    )

    for outcome in run.outcomes:
        conn.execute(
            "INSERT OR REPLACE INTO collection_run_collector "
            "(run_id, collector_id, entity_kind, outcome, reason, "
            " entities_with_data, entities_without_data, provides) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run.run_id,
                outcome.collector_id,
                str(outcome.entity_kind),
                outcome.outcome,
                outcome.reason,
                outcome.entities_with_data,
                outcome.entities_without_data,
                json.dumps(list(outcome.provides)),
            ),
        )
        for path in outcome.provides:
            conn.execute(
                "INSERT OR REPLACE INTO collection_run_path (run_id, path, collector_id) "
                "VALUES (?, ?, ?)",
                (run.run_id, path, outcome.collector_id),
            )

    conn.commit()


def read_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    """The run record, shaped as contracts/schemas/collection-run.json."""
    row = conn.execute(
        "SELECT * FROM collection_run WHERE run_id = ?", (run_id,)
    ).fetchone()
    if row is None:
        return None

    collectors = []
    for c in conn.execute(
        "SELECT * FROM collection_run_collector WHERE run_id = ? ORDER BY collector_id",
        (run_id,),
    ):
        entry: dict[str, Any] = {
            "collector_id": c["collector_id"],
            "entity_kind": c["entity_kind"],
            "outcome": c["outcome"],
            "provides": json.loads(c["provides"]),
        }
        if c["reason"] is not None:
            entry["reason"] = c["reason"]
        if c["entities_with_data"] is not None:
            entry["entities_with_data"] = c["entities_with_data"]
        if c["entities_without_data"] is not None:
            entry["entities_without_data"] = c["entities_without_data"]
        collectors.append(entry)

    out: dict[str, Any] = {
        "run_id": row["run_id"],
        "slate_id": row["slate_id"],
        "started_at": row["started_at"],
        "collectors": collectors,
    }
    if row["completed_at"] is not None:
        out["completed_at"] = row["completed_at"]
    return out


def latest_run(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT run_id FROM collection_run ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    return row["run_id"] if row else None


@dataclass(frozen=True)
class PathProvenance:
    """What happened to one feature path on one run."""

    path: str
    collector_id: str | None
    outcome: str | None
    reason: str | None = None
    entities_without_data: int | None = None

    @property
    def explanation(self) -> str:
        if self.collector_id is None:
            return (
                f"{self.path}: no registered collector provided this path on that run"
            )
        if self.outcome == "failed":
            return (
                f"{self.path}: collector {self.collector_id!r} failed ({self.reason}). "
                f"Whether data exists was never established — this is worth retrying."
            )
        if self.outcome == "not_invoked":
            return (
                f"{self.path}: collector {self.collector_id!r} was not invoked, because "
                f"no active model declared anything it provides."
            )
        return (
            f"{self.path}: collector {self.collector_id!r} succeeded and had nothing "
            f"for this entity. The data is genuinely absent, not merely unfetched."
        )


def explain_missing_path(
    conn: sqlite3.Connection, run_id: str, path: str
) -> PathProvenance:
    """Why a feature was missing on a given run.

    This is the read that justifies the table. "No score" is a fact the score store
    already implies by omission; which KIND of no-score it was is only recoverable
    from here.
    """
    row = conn.execute(
        "SELECT c.collector_id, c.outcome, c.reason, c.entities_without_data "
        "FROM collection_run_path p "
        "JOIN collection_run_collector c "
        "  ON c.run_id = p.run_id AND c.collector_id = p.collector_id "
        "WHERE p.run_id = ? AND p.path = ?",
        (run_id, path),
    ).fetchone()

    if row is None:
        return PathProvenance(path=path, collector_id=None, outcome=None)

    return PathProvenance(
        path=path,
        collector_id=row["collector_id"],
        outcome=row["outcome"],
        reason=row["reason"],
        entities_without_data=row["entities_without_data"],
    )
