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
for src in sorted(ROOT.glob("packages/*/src")) + sorted(ROOT.glob("packages/models/*/src")):
    sys.path.insert(0, str(src))

from xfun_composition import AliasResolver, compose_all, load_recipes
from xfun_ingestion import FixtureFileAdapter, ingest
from xfun_model_odds_spread import MODEL as ODDS_SPREAD
from xfun_model_over_under_lean import MODEL as OVER_UNDER_LEAN
from xfun_runtime import Registry, calibrate, run_models
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


def build_registry() -> Registry:
    """The only place that knows which models exist.

    Adding a model is one import and one register() call -- nothing else in the
    system changes.
    """
    registry = Registry()
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

    result = ingest(conn, FixtureFileAdapter())
    say(f"  ingestion    {result.summary()}")

    snapshots = load_snapshots(conn)
    say(f"  snapshots    {len(snapshots)} assembled from canonical entities")

    registry = build_registry()
    register_models(conn, registry)

    run = run_models(registry, snapshots, computed_at=STAMP)
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
