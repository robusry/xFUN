"""Determinism, and the two ways this model is allowed to say nothing.

The contract requires models to be pure, so identical input must produce identical
output -- this is the test that would catch a model reaching for the clock or a random
seed. The rest is about coverage: this is the first model whose signal can be genuinely
absent because a team has not played five matches, rather than because a fixture file
was written to omit it.
"""

from __future__ import annotations

from xfun_contract import MatchSnapshot
from xfun_model_recent_goals_total import MODEL

HOME = "signals.form.home.goals_scored_last_5"
AWAY = "signals.form.away.goals_scored_last_5"


def snapshot(home: int | None, away: int | None) -> MatchSnapshot:
    form: dict[str, dict[str, int]] = {}
    if home is not None:
        form["home"] = {"goals_scored_last_5": home}
    if away is not None:
        form["away"] = {"goals_scored_last_5": away}
    return MatchSnapshot(
        {
            "match_id": "epl-2026-08-15-ars-liv",
            "league": {"id": "epl", "name": "Premier League"},
            "kickoff_utc": "2026-08-15T19:00:00Z",
            "home_team": {"id": "ars", "name": "Arsenal"},
            "away_team": {"id": "liv", "name": "Liverpool"},
            "signals": {"form": form},
        }
    )


def test_identical_input_produces_identical_output():
    subject = snapshot(8, 5)
    first = MODEL.score(subject)
    second = MODEL.score(subject)
    assert first.raw_score == second.raw_score
    assert dict(first.components) == dict(second.components)


def test_the_score_is_the_two_sides_added():
    result = MODEL.score(snapshot(8, 5))
    assert result.raw_score == 13.0
    assert result.components == {"home_goals_last_5": 8.0, "away_goals_last_5": 5.0}


def test_components_keep_the_two_sides_apart():
    """24 from 12 + 12 is a different match from 24 from 22 + 2, and the raw score
    cannot tell them apart. The components are what makes the score arguable."""
    balanced = MODEL.score(snapshot(12, 12))
    lopsided = MODEL.score(snapshot(22, 2))
    assert balanced.raw_score == lopsided.raw_score
    assert dict(balanced.components) != dict(lopsided.components)


def test_a_goalless_pair_is_a_score_not_an_absence():
    """Zero is a real answer: two sides that have not scored in five matches. It must
    not be confused with the missing case below."""
    result = MODEL.score(snapshot(0, 0))
    assert result.raw_score == 0.0


def test_a_missing_side_is_a_skip_rather_than_a_score():
    """The runtime never calls `score` here -- it skips the match and records the path.
    This asserts the declaration that makes that happen, since a model that declared
    only the home path would silently score half a match."""
    assert set(MODEL.required_features) == {HOME, AWAY}
    assert snapshot(8, None).missing_features(MODEL.required_features) == (AWAY,)
    assert snapshot(None, None).missing_features(MODEL.required_features) == (HOME, AWAY)


def test_declares_identity_and_features():
    assert MODEL.model_id == "recent-goals-total"
    assert MODEL.model_version.count(".") == 2
    assert MODEL.required_features


def test_reads_collected_signals_without_knowing_their_producer():
    """Every declared path is a signal, and none of them names goal.com or the
    collector that fetched it. That indirection is what lets the producer change."""
    assert all(path.startswith("signals.form.") for path in MODEL.required_features)

    module = __import__("xfun_model_recent_goals_total")
    assert not any(name.startswith("xfun_collector") for name in dir(module))


def test_raw_score_is_not_normalised():
    """Models must not normalise -- the platform percentile-ranks. A model quietly
    returning 0..1 would look correct and destroy the cohort ranking's resolution."""
    assert MODEL.score(snapshot(14, 11)).raw_score == 25.0
