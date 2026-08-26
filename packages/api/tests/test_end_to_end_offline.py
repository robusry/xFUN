"""The whole pipeline, end to end, with no network.

This is CI's end-to-end check. It runs the real `run_pipeline` -- the same function
`scripts/pipeline.py` calls -- and supplies the four things a live run gets from
elsewhere: the clock, the collector's page source, how canonical matches reach the
store, and the slate rule. Everything below those four arguments is the code a live
run executes, which is the point. A change that made this test pass by taking a
different route through the system would have removed its value.

The captured inputs, and the fixed anchor they are read against, come from
`tests/harness.py` -- shared with `scripts/check_api_conformance.py` so that "the
pipeline, offline" has one description rather than two. That anchor is the thing here
most likely to be mistaken for a bug; it is not the hardcoded dates `use-real-dates`
removed from the live path, and the harness says why at length.

Note what is asserted and what is not. Reproducibility constrains what a run STORES,
not the route it takes to get there. The second run legitimately reuses persisted
collector output instead of collecting it again, so the run record differs on the
first repeat and is stable from then on. The scores and timestamps never move.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests"))

from harness import (
    OFFLINE_STAMP,
    load_pipeline,
    offline_arguments,
)

EXPECTED_SCORES = {
    "epl-2026-08-18-che-mun": 23.0,
    "epl-2026-08-15-ars-liv": 19.0,
    "laliga-2026-08-16-rma-get": 18.0,
    "epl-2026-08-15-bha-eve": 17.0,
    "epl-2026-08-16-new-bre": 15.0,
    "epl-2026-08-17-mci-tot": 14.0,
    "epl-2026-08-16-bur-shu": 12.0,
}
"""`recent-goals-total`'s raw scores from the captured pages -- goals both sides
scored across their last five completed matches, added.

The VALUES are asserted, not merely which matches got one. Asserting coverage alone
lets a broken arithmetic change through: swapping the model's `+` for a `-` leaves
exactly this set of matches scored, and an earlier version of this test passed
against that. Three runs agreeing on a wrong answer is still a wrong answer.

`seriea-2026-08-16-int-tor` is absent on purpose: the source calls Inter `Inter` and
the snapshot calls them `Internazionale`, so the scan cannot recognise them and the
match comes back with a recorded reason and no score. That is the partial-coverage
path, exercised on real captured data."""

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
    pipeline = load_pipeline()

    import xfun_store.db as db_module

    real_connect = db_module.connect
    states = []
    try:
        db_module.connect = lambda path=None: real_connect(db)
        pipeline.connect = db_module.connect
        for _ in range(3):
            assert pipeline.run_pipeline(**offline_arguments(pipeline)) == 0
            states.append(_snapshot(db))
    finally:
        db_module.connect = real_connect
    return states


def test_the_pipeline_produces_the_expected_scores(three_runs):
    """Correctness, not only stability. Three runs agreeing proves nothing alone."""
    produced = {
        row[0]: row[4]
        for row in three_runs[0]["scores"]
        if row[1] == "recent-goals-total" and row[4] is not None
    }

    assert produced == EXPECTED_SCORES
    assert "seriea-2026-08-16-int-tor" not in produced, (
        "Inter is unrecognisable to the source by the snapshot's name; this match "
        "must come back unscored rather than scored from a partial sum"
    )


def test_scores_never_move(three_runs):
    first, second, third = three_runs
    assert first["scores"] == second["scores"] == third["scores"]
    assert first["scores"], "the offline check should produce scores at all"


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
    """A clock-driven anchor would store today, and break the captured scan."""
    stored_stamp = three_runs[0]["runs"][0][2]
    assert stored_stamp == OFFLINE_STAMP


def test_a_real_runs_clock_is_distinct_per_run():
    """And the pipeline's own clock does the opposite, without touching the network."""
    pipeline = load_pipeline()

    first = pipeline.RunClock.now()
    second = pipeline.RunClock.now()

    assert first.stamp != OFFLINE_STAMP
    assert first.run_id.startswith("run-")
    assert first.as_of is None, "live scans anchor to the clock, not a fixed date"
    assert second.stamp >= first.stamp, "run stamps must sort chronologically"


def test_the_pipeline_offers_no_offline_mode():
    """The seam is an argument, never a flag.

    If someone reintroduces `--live` or an `--offline`, this fails. The whole point of
    the change that removed them is that a mode a person can select is a mode that
    drifts away from the one CI exercises.
    """
    import subprocess

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "pipeline.py"), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--live" not in result.stdout
    assert "--offline" not in result.stdout
    assert "--fixtures" not in result.stdout
