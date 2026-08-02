"""Determinism: identical fixture input must produce identical output.

The contract requires models to be pure. This is the test that would catch a
model reaching for the clock, a random seed, or anything else outside its
snapshot.
"""

from __future__ import annotations

import json

from xfun_contract import MatchSnapshot
from xfun_model_over_under_lean import MODEL
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
    assert MODEL.model_id == "over-under-lean"
    assert MODEL.model_version.count(".") == 2
    assert MODEL.required_features
    assert "PLACEHOLDER" in MODEL.description


def test_components_are_numeric_and_explain_the_score():
    for snapshot in _scoreable():
        result = MODEL.score(snapshot)
        assert result.components, "a bare score is a thing to distrust"
        for name, value in result.components.items():
            assert isinstance(value, (int, float)), name
