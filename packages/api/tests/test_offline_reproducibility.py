"""The offline path stores the same thing every time it runs.

This is the test that fails if someone decides the fixture path's fixed anchor is
the bug that `use-real-dates` forgot to fix. It is not: the captured result pages
exist only for a bounded range of dates, so a scan anchored to the present walks off
the end of them, and CI compares against golden output that a moving clock would
invalidate daily.

Note what is asserted and what is not. Reproducibility constrains what a run STORES,
not the route it takes to get there. The second run legitimately reuses persisted
collector output instead of collecting it again, so the run record differs on the
first repeat and is stable from then on. The scores and timestamps never move.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

STORED = {
    "scores": "SELECT match_id, model_id, model_version, snapshot_hash, raw_score, "
    "computed_at FROM model_score ORDER BY match_id, model_id, snapshot_hash",
    "runs": "SELECT run_id, slate_id, started_at, completed_at FROM collection_run "
    "ORDER BY run_id",
    "outcomes": "SELECT run_id, collector_id, outcome, entities_with_data, "
    "entities_without_data FROM collection_run_collector ORDER BY run_id, collector_id",
    "corpus": "SELECT collector_id, entity_id, values_json, collected_at "
    "FROM collector_corpus ORDER BY collector_id, entity_id, collected_at",
}


def _load_pipeline():
    """Import scripts/pipeline.py, which is a script rather than a package."""
    spec = importlib.util.spec_from_file_location(
        "_xfun_pipeline", ROOT / "scripts" / "pipeline.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["_xfun_pipeline"] = module
    spec.loader.exec_module(module)
    return module


def _snapshot(db: Path) -> dict[str, list]:
    conn = sqlite3.connect(db)
    try:
        return {name: conn.execute(sql).fetchall() for name, sql in STORED.items()}
    finally:
        conn.close()


@pytest.fixture(scope="module")
def three_runs(tmp_path_factory):
    """Run the real pipeline three times against one throwaway database."""
    db = tmp_path_factory.mktemp("repro") / "xfun.db"
    pipeline = _load_pipeline()

    import xfun_store.db as db_module

    real_connect = db_module.connect
    original_argv = sys.argv
    states = []
    try:
        db_module.connect = lambda path=None: real_connect(db)
        pipeline.connect = db_module.connect
        sys.argv = ["pipeline.py", "--quiet"]
        for _ in range(3):
            assert pipeline.main() == 0
            states.append(_snapshot(db))
    finally:
        db_module.connect = real_connect
        sys.argv = original_argv
    return states


def test_scores_never_move(three_runs):
    first, second, third = three_runs
    assert first["scores"] == second["scores"] == third["scores"]
    assert first["scores"], "the fixture path should produce scores at all"


def test_timestamps_and_run_ids_never_move(three_runs):
    """The property the fixed anchor exists to provide."""
    first, second, third = three_runs
    assert first["runs"] == second["runs"] == third["runs"]
    assert len(first["runs"]) == 1, "repeated offline runs are one run, not three"


def test_the_corpus_is_written_once_and_not_duplicated(three_runs):
    first, second, third = three_runs
    assert first["corpus"] == second["corpus"] == third["corpus"]


def test_the_run_record_reflects_reuse_then_holds_steady(three_runs):
    """Reproducible in what it stores, honest about what it did.

    Run one collects; run two finds the corpus fresh and reuses it. That is the
    corpus feature working, not determinism breaking -- and from run two onward
    nothing changes at all.
    """
    first, second, third = three_runs

    def outcome(state, collector_id):
        return next(r[2] for r in state["outcomes"] if r[1] == collector_id)

    assert outcome(first, "recent-results") == "succeeded"
    assert outcome(second, "recent-results") == "reused"
    assert second["outcomes"] == third["outcomes"], "no steady state reached"


def test_the_offline_stamp_is_the_anchor_not_the_clock(three_runs):
    """A clock-driven fixture path would store today, and break the captured scan."""
    pipeline = _load_pipeline()
    clock = pipeline.RunClock.for_run(live=False)

    assert clock.stamp == pipeline.OFFLINE_STAMP
    assert clock.run_id == pipeline.OFFLINE_RUN_ID
    assert clock.as_of == pipeline.OFFLINE_AS_OF

    stored_stamp = three_runs[0]["runs"][0][2]
    assert stored_stamp == pipeline.OFFLINE_STAMP


def test_the_live_clock_is_distinct_per_run():
    """And the live path does the opposite, without touching the network."""
    pipeline = _load_pipeline()

    first = pipeline.RunClock.for_run(live=True)
    second = pipeline.RunClock.for_run(live=True)

    assert first.stamp != pipeline.OFFLINE_STAMP
    assert first.run_id.startswith("run-")
    assert first.as_of is None, "live scans anchor to the clock, not a fixed date"
    assert second.stamp >= first.stamp, "run stamps must sort chronologically"
