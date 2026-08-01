"""Reading and writing the append-only score store.

There is no `update_score` and no `delete_score`, and there never will be. The
database enforces this with triggers; this module simply has no way to express it.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence

from xfun_contract import ModelScore

__all__ = ["all_scores", "latest_scores", "register_models", "write_scores"]


def write_scores(conn: sqlite3.Connection, scores: Iterable[ModelScore]) -> int:
    """Insert scores. Re-scoring the same snapshot is a no-op rather than an error,
    since the primary key already encodes 'this model version saw this exact input'."""
    rows = [
        (
            s.match_id,
            s.model_id,
            s.model_version,
            s.snapshot_hash,
            s.raw_score,
            json.dumps(dict(s.components), sort_keys=True),
            s.computed_at or "",
        )
        for s in scores
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO model_score "
        "(match_id, model_id, model_version, snapshot_hash, raw_score, components, computed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(rows)


def _to_model_scores(rows: Iterable[sqlite3.Row]) -> tuple[ModelScore, ...]:
    return tuple(
        ModelScore(
            match_id=r["match_id"],
            model_id=r["model_id"],
            model_version=r["model_version"],
            raw_score=r["raw_score"],
            components=json.loads(r["components"]),
            snapshot_hash=r["snapshot_hash"],
            computed_at=r["computed_at"] or None,
        )
        for r in rows
    )


def latest_scores(
    conn: sqlite3.Connection,
    *,
    match_ids: Sequence[str] | None = None,
) -> tuple[ModelScore, ...]:
    """The current score per (match, model), for serving.

    Superseded rows stay in the base table for evaluation and audit; this view is
    what the API reads.
    """
    sql = "SELECT * FROM latest_model_score"
    params: list[str] = []
    if match_ids:
        sql += f" WHERE match_id IN ({','.join('?' * len(match_ids))})"
        params = list(match_ids)
    return _to_model_scores(conn.execute(sql, params))


def all_scores(conn: sqlite3.Connection) -> tuple[ModelScore, ...]:
    """Every row ever written, superseded ones included. For evaluation and audit."""
    return _to_model_scores(conn.execute("SELECT * FROM model_score ORDER BY computed_at"))


def register_models(conn: sqlite3.Connection, registry) -> None:
    """Mirror the in-process registry into the database so the public registry
    endpoint can report models -- including retired ones -- without importing any
    model package."""
    conn.executemany(
        "INSERT INTO model_registry (model_id, model_version, description, retired, features) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(model_id) DO UPDATE SET "
        " model_version=excluded.model_version, description=excluded.description, "
        " retired=excluded.retired, features=excluded.features",
        [
            (
                r.model.model_id,
                r.model.model_version,
                r.model.description,
                1 if r.retired else 0,
                json.dumps(list(r.model.required_features)),
            )
            for r in registry.all()
        ],
    )
    conn.commit()
