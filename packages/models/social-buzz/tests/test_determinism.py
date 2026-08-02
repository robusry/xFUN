"""Determinism: identical fixture input must produce identical output.

The contract requires models to be pure. This is the test that would catch a model
reaching for the clock, a random seed, or anything else outside its snapshot.

For this model it also checks something the other two cannot: that a model consuming
COLLECTED signals is no less pure than one consuming canonical data. The values
arrive as paths on the snapshot, so scoring is reproducible from the fixture alone
with no collector in sight.
"""

from __future__ import annotations

import json

from xfun_contract import MatchSnapshot
from xfun_model_social_buzz import MODEL
from xfun_runtime.paths import fixtures_dir


def _scoreable() -> list[MatchSnapshot]:
    paths = sorted((fixtures_dir() / "snapshots").glob("*.json"))
    snapshots = [MatchSnapshot(json.loads(p.read_text())) for p in paths]
    return [s for s in snapshots if s.has_features(MODEL.required_features)]


def test_fixtures_exercise_this_model():
    assert _scoreable(), "no fixture provides this model's required features"


def test_identical_input_produces_identical_output():
    for snapshot in _scoreable():
        first = MODEL.score(snapshot)
        second = MODEL.score(snapshot)
        assert first.raw_score == second.raw_score
        assert dict(first.components) == dict(second.components)


def test_declares_identity_and_features():
    assert MODEL.model_id == "social-buzz"
    assert MODEL.model_version.count(".") == 2
    assert MODEL.required_features
    assert "PLACEHOLDER" in MODEL.description


def test_components_are_numeric_and_explain_the_score():
    for snapshot in _scoreable():
        result = MODEL.score(snapshot)
        assert result.components, "a bare score is a thing to distrust"
        for name, value in result.components.items():
            assert isinstance(value, (int, float)), name


def test_reads_collected_signals_without_knowing_their_producer():
    """Every declared path is a signal. The model names paths, never collectors."""
    assert all(p.startswith("signals.") for p in MODEL.required_features)

    module = __import__("xfun_model_social_buzz")
    assert not any(
        name.startswith("xfun_collector") for name in dir(module)
    ), "a model must not reach for a collector"


def test_raw_score_is_not_normalised():
    """Models must not normalise -- the platform percentile-ranks. A model quietly
    returning 0..1 would look correct and destroy the cohort ranking's resolution."""
    scores = [MODEL.score(s).raw_score for s in _scoreable()]
    assert any(value > 1.0 for value in scores), "this model's scale is not 0..1"
