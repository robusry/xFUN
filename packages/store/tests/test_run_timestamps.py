"""Where "now" comes from, and what depends on it being distinct.

Two properties, pulling in opposite directions on purpose.

The fixture path must be REPRODUCIBLE: two runs over unchanged inputs produce
identical rows, identical timestamps, identical run ids. CI compares against golden
output, and `recent-results` scans backwards through captured pages that exist only
for a bounded range of dates -- anchored to today it would walk off the end of them
and report an absence that is an artefact of the anchor.

The live path must be DISTINGUISHABLE: two runs are two records, and "most recent by
computed_at" has to mean something. With one constant timestamp every generation
ties and the winner is insertion order.
"""

from __future__ import annotations

import pytest
from xfun_store import connect, latest_scores, migrate, write_scores

EARLIER = "2026-08-14T04:00:00+00:00"
LATER = "2026-08-24T09:30:00+00:00"


class _Score:
    """Structural stand-in for ModelScore; write_scores reads attributes."""

    def __init__(self, snapshot_hash: str, raw_score: float, computed_at: str) -> None:
        self.match_id = "epl-2026-08-15-ars-liv"
        self.model_id = "recent-goals-total"
        self.model_version = "1.0.0"
        self.snapshot_hash = snapshot_hash
        self.raw_score = raw_score
        self.components: dict[str, float] = {}
        self.computed_at = computed_at


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "timestamps.db")
    list(migrate(c))
    yield c
    c.close()


def test_a_later_score_supersedes_an_earlier_one(conn):
    """The serving read this change makes meaningful again."""
    write_scores(conn, [_Score("hash-a", 3.0, EARLIER)])
    write_scores(conn, [_Score("hash-b", 7.0, LATER)])

    current = latest_scores(conn)
    for_match = [s for s in current if s.match_id == "epl-2026-08-15-ars-liv"]

    assert len(for_match) == 1, "a serving read resolves to one row per model"
    assert for_match[0].raw_score == 7.0, "the later computed_at should win"


def test_rescoring_the_same_snapshot_is_a_no_op(conn):
    """Identical input, identical row -- reproducibility, not a new generation."""
    write_scores(conn, [_Score("hash-a", 3.0, EARLIER)])
    write_scores(conn, [_Score("hash-a", 3.0, EARLIER)])

    rows = conn.execute("SELECT COUNT(*) AS n FROM model_score").fetchone()
    assert rows["n"] == 1


def test_both_generations_remain_queryable(conn):
    """Superseded rows stay: the store is append-only, and evaluation needs them."""
    write_scores(conn, [_Score("hash-a", 3.0, EARLIER)])
    write_scores(conn, [_Score("hash-b", 7.0, LATER)])

    rows = conn.execute("SELECT COUNT(*) AS n FROM model_score").fetchone()
    assert rows["n"] == 2


def test_two_distinct_runs_do_not_overwrite_each_other(conn):
    """The `run_id="demo"` behaviour this change removes from the live path."""
    for run_id, stamp in (("run-a", EARLIER), ("run-b", LATER)):
        conn.execute(
            "INSERT OR REPLACE INTO collection_run "
            "(run_id, slate_id, selection, started_at) VALUES (?, ?, '{}', ?)",
            (run_id, "slate-1", stamp),
        )
    conn.commit()

    rows = conn.execute("SELECT run_id FROM collection_run ORDER BY started_at").fetchall()
    assert [r["run_id"] for r in rows] == ["run-a", "run-b"]


def test_a_repeated_reproducible_run_is_one_record_not_two(conn):
    """The fixture path keeps a constant id on purpose: the same run repeated is
    one run, not two, and the offline demo must not accumulate records."""
    for _ in range(2):
        conn.execute(
            "INSERT OR REPLACE INTO collection_run "
            "(run_id, slate_id, selection, started_at) VALUES ('demo', 'slate-1', '{}', ?)",
            (EARLIER,),
        )
    conn.commit()

    rows = conn.execute("SELECT COUNT(*) AS n FROM collection_run").fetchone()
    assert rows["n"] == 1
