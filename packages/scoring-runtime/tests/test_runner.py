"""The runner's two load-bearing properties: order independence and honest skips."""

from __future__ import annotations

import json

import pytest
from xfun_contract import MatchSnapshot, ScoreResult
from xfun_model_odds_spread import MODEL as ODDS_SPREAD
from xfun_model_over_under_lean import MODEL as OVER_UNDER_LEAN
from xfun_runtime import RegistrationError, Registry, calibrate, run_models
from xfun_runtime.calibration import CohortNotImplemented
from xfun_runtime.paths import fixtures_dir


@pytest.fixture
def snapshots() -> list[MatchSnapshot]:
    paths = sorted((fixtures_dir() / "snapshots").glob("*.json"))
    return [MatchSnapshot(json.loads(p.read_text())) for p in paths]


@pytest.fixture
def registry() -> Registry:
    reg = Registry()
    reg.register(OVER_UNDER_LEAN)
    reg.register(ODDS_SPREAD)
    return reg


def test_models_run_in_any_order_with_identical_results(registry, snapshots):
    """Models never read each other, so ordering must not matter."""
    forward = run_models(registry, snapshots, computed_at="T")
    reversed_ = run_models(registry, list(reversed(snapshots)), computed_at="T")

    assert sorted(s.to_dict().items().__str__() for s in forward.scores) == sorted(
        s.to_dict().items().__str__() for s in reversed_.scores
    )


def test_missing_features_produce_a_recorded_skip_not_silence(registry, snapshots):
    """A match with no odds is skipped by both models, with reasons captured."""
    result = run_models(registry, snapshots, computed_at="T")

    skipped = {(s.match_id, s.model_id) for s in result.skips}
    assert ("seriea-2026-08-16-int-tor", "over-under-lean") in skipped
    assert ("seriea-2026-08-16-int-tor", "odds-spread") in skipped

    for skip in result.skips:
        assert skip.missing_features, "a skip must say what was missing"
        assert skip.reason


def test_partial_coverage_scores_one_model_and_skips_the_other(registry, snapshots):
    """The la liga fixture has a total line but no moneyline, on purpose."""
    result = run_models(registry, snapshots, computed_at="T")
    match_id = "laliga-2026-08-16-rma-get"

    scored = {s.model_id for s in result.scores if s.match_id == match_id}
    skipped = {s.model_id for s in result.skips if s.match_id == match_id}

    assert scored == {"over-under-lean"}
    assert skipped == {"odds-spread"}


def test_scores_carry_the_hash_of_their_input(registry, snapshots):
    result = run_models(registry, snapshots, computed_at="T")
    by_id = {s.match_id: s for s in snapshots}

    for score in result.scores:
        assert score.snapshot_hash == by_id[score.match_id].hash


def test_registration_rejects_features_absent_from_the_schema():
    """A typo in required_features must fail loudly at registration, not quietly
    skip every match forever."""

    class Typo:
        model_id = "typo"
        model_version = "0.1.0"
        required_features = ("odds.total_lien",)
        description = "x"

        def score(self, snapshot):  # pragma: no cover - never called
            return ScoreResult(raw_score=0.0)

    with pytest.raises(RegistrationError, match="absent from"):
        Registry().register(Typo())


def test_calibration_ranks_each_model_against_itself(registry, snapshots):
    result = run_models(registry, snapshots, computed_at="T")
    calibrated = calibrate(result.scores, cohort="window")

    for score in calibrated.scores:
        assert 0.0 <= score.calibrated_score <= 100.0

    assert calibrated.cohort.definition == "window"
    assert calibrated.cohort.match_count > 0


def test_tied_raw_scores_calibrate_identically(registry, snapshots):
    """Two matches on the same total line must not be separated by sort order."""
    result = run_models(registry, snapshots, computed_at="T")
    calibrated = calibrate(result.scores, cohort="window")

    lean = [s for s in calibrated.scores if s.model_id == "over-under-lean"]
    tied = [s for s in lean if s.raw_score == 3.0]

    assert len(tied) == 2, "fixtures should contain two matches on a 3.0 line"
    assert tied[0].calibrated_score == tied[1].calibrated_score


@pytest.mark.parametrize("cohort", ["league", "season", "global"])
def test_unimplemented_cohorts_fail_loudly(registry, snapshots, cohort):
    """A cohort we have not built must raise, never silently fall back."""
    result = run_models(registry, snapshots, computed_at="T")

    with pytest.raises(CohortNotImplemented):
        calibrate(result.scores, cohort=cohort)
