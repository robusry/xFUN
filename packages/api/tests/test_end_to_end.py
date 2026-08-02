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
from xfun_runtime import Registry, run_models
from xfun_store import connect, migrate, register_models, write_scores

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

    registry = Registry()
    registry.register(OVER_UNDER_LEAN)
    registry.register(ODDS_SPREAD)
    register_models(conn, registry)
    write_scores(
        conn, run_models(registry, load_snapshots(conn), computed_at="2026-08-14T04:00:00Z").scores
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


def test_partial_coverage_renormalises_and_says_so(api_client):
    """One model scored this match, the other could not."""
    body = api_client.get("/v1/matches/laliga-2026-08-16-rma-get/scores").json()

    assert body["composed"]["value"] is not None
    assert "renormalized" in body["composed"]["reason"]
    assert len(body["model_scores"]) == 1


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
    assert model_ids == {"over-under-lean", "odds-spread"}
    for score in body["model_scores"]:
        assert score["components"], "explanations, not bare numbers"


def test_registry_lists_models_compositions_and_aliases(api_client):
    body = api_client.get("/v1/registry").json()

    assert {m["model_id"] for m in body["models"]} == {"over-under-lean", "odds-spread"}
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
    recipes = load_recipes(known_model_ids={"over-under-lean", "odds-spread"})
    resolver = AliasResolver(recipes, model_ids={})
    assert resolver.resolve("default").kind == "composition"
