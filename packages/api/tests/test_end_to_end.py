"""One fixture match, all the way through: file -> entities -> snapshot -> model
-> store -> calibration -> composition -> HTTP response.

If this passes, the seams hold. It is the test that would catch a tier boundary
quietly breaking, which no unit test can see.
"""

from __future__ import annotations

import os

import pytest
from xfun_composition import AliasResolver, load_recipes
from xfun_ingestion import fixture_payloads, ingest
from xfun_model_odds_spread import MODEL as ODDS_SPREAD
from xfun_model_over_under_lean import MODEL as OVER_UNDER_LEAN
from xfun_model_recent_goals_total import MODEL as RECENT_GOALS_TOTAL
from xfun_runtime import Registry, run_models
from xfun_store import connect, migrate, register_models, write_scores

# What a collection run would have joined onto these matches. Hand-written rather
# than collected, because this test is about the seams either side of collection --
# `recent-results` has its own tests, and one of them runs the real scan over the
# golden captures.
#
# Deliberately uneven. `ars-liv` carries both sides, `rma-get` carries none, and that
# is what makes the two coverage cases below real rather than contrived.
COLLECTED_SIGNALS = {
    "epl-2026-08-15-ars-liv": {
        "form": {
            "home": {"goals_scored_last_5": 9},
            "away": {"goals_scored_last_5": 7},
        }
    },
    "epl-2026-08-16-new-bre": {
        "form": {
            "home": {"goals_scored_last_5": 4},
            "away": {"goals_scored_last_5": 5},
        }
    },
    "epl-2026-08-17-mci-tot": {
        # One side only: Tottenham has not played five completed matches. The model
        # requires both, so this match is skipped with the away path named.
        "form": {"home": {"goals_scored_last_5": 12}}
    },
}

# Locally, skip if FastAPI is absent so someone can run the rest of the suite on a
# fresh clone without `uv sync`. In CI, import hard and fail.
#
# The distinction is not fussiness. An earlier version skipped unconditionally,
# and when CI installed only the workspace root, these eight tests vanished while
# the Tests step still reported green -- a materially weaker suite passing
# silently. A skip that is invisible is worse than a failure.
if os.environ.get("CI"):
    import fastapi  # noqa: F401
else:
    pytest.importorskip("fastapi", reason="API tests need `uv sync`")


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """A fully populated API backed by a throwaway database."""
    db = tmp_path / "e2e.db"

    def fake_connect(path=None):
        return connect(db)

    monkeypatch.setattr("xfun_store.db.connect", fake_connect)
    monkeypatch.setattr("xfun_api.context.connect", fake_connect)

    conn = connect(db)
    list(migrate(conn))
    ingest(conn, fixture_payloads())

    from xfun_store import load_snapshots

    registry = Registry(provided_paths=RECENT_GOALS_TOTAL.required_features)
    registry.register(OVER_UNDER_LEAN)
    registry.register(ODDS_SPREAD)
    registry.register(RECENT_GOALS_TOTAL)
    register_models(conn, registry)
    snapshots = load_snapshots(conn, signals=COLLECTED_SIGNALS)
    write_scores(
        conn, run_models(registry, snapshots, computed_at="2026-08-14T04:00:00Z").scores
    )
    conn.close()

    import xfun_api.context as context_module
    from fastapi.testclient import TestClient

    context_module._build_context.cache_clear()
    from xfun_api import app

    yield TestClient(app)
    context_module._build_context.cache_clear()


def test_a_fixture_match_reaches_the_api_with_a_score(api_client):
    response = api_client.get("/v1/matches", params={"from": "2026-08-01", "to": "2026-08-31"})
    assert response.status_code == 200

    body = response.json()
    assert body["matches"], "fixtures should produce matches"

    top = body["matches"][0]
    assert top["composed"]["value"] is not None
    assert top["composed"]["contributors"], "a score must say what produced it"


def test_every_response_states_its_cohort_and_alias(api_client):
    """A calibrated score without its cohort is uninterpretable, and an alias can
    be repointed, so both must travel with the numbers."""
    body = api_client.get(
        "/v1/matches", params={"from": "2026-08-01", "to": "2026-08-31"}
    ).json()

    assert body["cohort"]["definition"] == "window"
    assert body["cohort"]["match_count"] > 0
    assert body["score_alias"]["alias"] == "default"
    assert body["score_alias"]["resolves_to"].startswith("default-v")


def test_a_model_outside_the_recipe_still_has_its_score_served(api_client):
    """`rma-get` has an over/under line but no prices and no collected form, so
    exactly one model scored it -- and that model is not in the default recipe.

    Its score is still stored and served per-model, while the composed value is null
    with a reason. Per-model scores are not a by-product of composition: a consumer
    blending its own way needs them whatever the recipe happens to name today."""
    body = api_client.get("/v1/matches/laliga-2026-08-16-rma-get/scores").json()

    assert [s["model_id"] for s in body["model_scores"]] == ["over-under-lean"]
    assert body["composed"]["value"] is None
    assert "recent-goals-total" in body["composed"]["reason"]


def test_an_unscored_match_is_returned_with_a_reason_not_dropped(api_client):
    body = api_client.get(
        "/v1/matches", params={"from": "2026-08-01", "to": "2026-08-31"}
    ).json()

    unscored = [m for m in body["matches"] if m["composed"]["value"] is None]
    assert unscored, "the no-odds fixture should appear with no score"
    assert unscored[0]["composed"]["reason"]


def test_per_model_scores_are_exposed_for_third_party_blending(api_client):
    body = api_client.get("/v1/matches/epl-2026-08-15-ars-liv/scores").json()

    model_ids = {s["model_id"] for s in body["model_scores"]}
    assert model_ids == {"over-under-lean", "odds-spread", "recent-goals-total"}
    for score in body["model_scores"]:
        assert score["components"], "explanations, not bare numbers"


def test_a_match_with_one_side_collected_is_returned_unscored_with_a_reason(api_client):
    """Tottenham carries no five-match total, so `recent-goals-total` never ran on
    this match. The match is still returned, and the composed score says why it has
    no value -- a shorter list would be a worse answer."""
    body = api_client.get("/v1/matches/epl-2026-08-17-mci-tot/scores").json()

    assert "recent-goals-total" not in {s["model_id"] for s in body["model_scores"]}
    assert body["composed"]["value"] is None
    assert body["composed"]["reason"]


def test_registry_lists_models_compositions_and_aliases(api_client):
    body = api_client.get("/v1/registry").json()

    assert {m["model_id"] for m in body["models"]} == {
        "over-under-lean",
        "odds-spread",
        "recent-goals-total",
    }
    assert any(a["alias"] == "default" for a in body["aliases"])
    assert body["compositions"][0]["on_missing"] == "renormalize"


@pytest.mark.parametrize("cohort", ["league", "season", "global"])
def test_unimplemented_cohorts_return_501_not_a_wrong_answer(api_client, cohort):
    response = api_client.get(
        "/v1/matches",
        params={"from": "2026-08-01", "to": "2026-08-31", "cohort": cohort},
    )
    assert response.status_code == 501
    assert "STUBS" in response.json()["detail"]


def test_recipes_reference_only_registered_models():
    """A recipe naming a model that does not exist must fail at load, not produce
    a quietly wrong composition."""
    recipes = load_recipes(
        known_model_ids={"over-under-lean", "odds-spread", "recent-goals-total"}
    )
    resolver = AliasResolver(recipes, model_ids={})
    assert resolver.resolve("default").kind == "composition"
