#!/usr/bin/env python3
"""Run the whole pipeline: migrate, ingest, score, persist.

This is the script the demo calls, and it is deliberately readable end to end --
a collaborator should be able to follow data from a fixture file to a stored score
without opening anything else.

Note where the tiers meet. Ingestion knows nothing about models. Models know
nothing about the store. The API (started separately) knows nothing about either;
it reads rows.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make workspace packages importable without `uv sync`, so this runs on a fresh
# clone. With uv sync installed editable, these are already on the path.
ROOT = Path(__file__).resolve().parent.parent
for src in (
    sorted(ROOT.glob("packages/*/src"))
    + sorted(ROOT.glob("packages/models/*/src"))
    + sorted(ROOT.glob("packages/collectors/*/src"))
):
    sys.path.insert(0, str(src))

from xfun_collector_fixture_signals import fixture_collectors
from xfun_composition import AliasResolver, compose_all, load_recipes
from xfun_ingestion import assemble_slate, fixture_payloads, ingest
from xfun_model_odds_spread import MODEL as ODDS_SPREAD
from xfun_model_over_under_lean import MODEL as OVER_UNDER_LEAN
from xfun_runtime import (
    CollectorRegistry,
    Registry,
    calibrate,
    run_collectors,
    run_models,
)
from xfun_store import (
    connect,
    latest_scores,
    load_snapshots,
    migrate,
    register_models,
    write_scores,
    write_snapshot_payload,  # noqa: F401  (re-exported for clarity)
)

STAMP = "2026-08-14T04:00:00+00:00"


def build_collector_registry() -> CollectorRegistry:
    """The only place that knows which collectors exist."""
    registry = CollectorRegistry()
    for collector in fixture_collectors():
        registry.register(collector)
    return registry


def build_registry(provided_paths: frozenset[str] = frozenset()) -> Registry:
    """The only place that knows which models exist.

    Adding a model is one import and one register() call -- nothing else in the
    system changes.

    `provided_paths` comes from the collector registry. A model declaring a signal
    nothing provides fails here rather than skipping every match in silence.
    """
    registry = Registry(provided_paths=provided_paths)
    registry.register(OVER_UNDER_LEAN)
    registry.register(ODDS_SPREAD)
    return registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    def say(*parts: object) -> None:
        if not args.quiet:
            print(*parts)

    conn = connect()

    applied = list(migrate(conn))
    say(f"  migrations   {len(applied)} applied" if applied else "  migrations   up to date")

    result = ingest(conn, fixture_payloads())
    say(f"  ingestion    {result.summary()}")

    # The slate is decided before any collector runs, because collectors fan out
    # from it -- a team-keyed collector needs to know which teams are in play.
    slate = assemble_slate(conn)
    say(f"  slate        {len(slate.matches)} matches, "
        f"{len(slate.teams())} teams, {len(slate.leagues())} leagues "
        f"({slate.selection.rule})")

    collectors = build_collector_registry()
    registry = build_registry(collectors.provided_paths())

    # Only what some active model actually declares gets collected. A source
    # nothing consumes is not fetched -- rate limits are real.
    required = {p for m in registry.active() for p in m.model.required_features}
    collection = run_collectors(collectors, slate, required, run_id="demo", started_at=STAMP)
    say(f"  collection   {collection.summary()}")
    for outcome in collection.outcomes:
        detail = outcome.reason or (
            f"{outcome.entities_with_data} with data, "
            f"{outcome.entities_without_data} without"
            if outcome.entities_with_data is not None
            else "no model declared anything it provides"
        )
        say(f"               {outcome.collector_id}: {outcome.outcome} — {detail}")

    # Signals are folded in before hashing, so a changed signal yields a new
    # snapshot_hash and therefore a new score row.
    snapshots = load_snapshots(conn, signals=collection.signals)
    say(f"  snapshots    {len(snapshots)} assembled from canonical entities")

    register_models(conn, registry)

    run = run_models(
        registry, snapshots, computed_at=STAMP, unavailable=collection.unavailable_paths()
    )
    write_scores(conn, run.scores)
    say(f"  scoring      {run.summary()}")
    for skip in run.skips:
        say(f"               skipped {skip.match_id} / {skip.model_id}: {skip.reason}")

    # Calibration and composition are shown here for the demo, but they are NOT
    # persisted -- the caller picks the cohort per request, so these are derived
    # at read time by the API.
    calibration = calibrate(latest_scores(conn), cohort="window")
    recipes = load_recipes(known_model_ids={m.model_id for m in registry.all()})
    AliasResolver(recipes, model_ids={m.model_id: m.model_id for m in registry.all()})
    composed = compose_all(
        calibration.by_match(),
        recipes["default"],
        match_ids=[s.match_id for s in snapshots],
    )

    say(f"\n  ranked ({calibration.cohort.definition} cohort, "
        f"{calibration.cohort.match_count} matches):")
    ordered = sorted(
        composed.items(),
        key=lambda kv: (kv[1].value is None, -(kv[1].value or 0)),
    )
    for match_id, score in ordered:
        value = f"{score.value:5.1f}" if score.value is not None else "    —"
        say(f"    {value}  {match_id}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
