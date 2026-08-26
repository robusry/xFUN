#!/usr/bin/env python3
"""Run the whole pipeline: acquire, collect, score, persist.

The entry point to the system, and deliberately readable end to end -- a collaborator
should be able to follow data from the schedule source to a stored score without
opening anything else.

This requires network access to the schedule source. There is no offline or
fixture-backed mode: `run_pipeline` takes its inputs as arguments, `main` supplies the
live ones, and the end-to-end test supplies captured ones. That is the whole of the
difference, and it exists so the thing a person runs and the thing CI exercises are
the same code rather than two systems that must be kept in step.

Note where the tiers meet. Acquisition knows nothing about models. Models know
nothing about the store. The API (started separately) knows nothing about either;
it reads rows.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

# Make workspace packages importable without `uv sync`, so this runs on a fresh
# clone. With uv sync installed editable, these are already on the path.
ROOT = Path(__file__).resolve().parent.parent
for src in (
    sorted(ROOT.glob("packages/*/src"))
    + sorted(ROOT.glob("packages/models/*/src"))
    + sorted(ROOT.glob("packages/collectors/*/src"))
):
    sys.path.insert(0, str(src))

from xfun_collector_recent_results import LivePages, RecentResults
from xfun_composition import AliasResolver, compose_all, load_recipes
from xfun_ingestion import assemble_slate
from xfun_ingestion.schedule import acquire_window
from xfun_model_odds_spread import MODEL as ODDS_SPREAD
from xfun_model_over_under_lean import MODEL as OVER_UNDER_LEAN
from xfun_model_recent_goals_total import MODEL as RECENT_GOALS_TOTAL
from xfun_runtime import (
    CollectorRegistry,
    Registry,
    calibrate,
    run_collectors,
    run_models,
)
from xfun_store import (
    connect,
    corpus_freshness,
    latest_scores,
    load_snapshots,
    migrate,
    read_corpus,
    register_models,
    write_collection_run,
    write_corpus,
    write_scores,
    write_snapshot_payload,  # noqa: F401  (re-exported for clarity)
)


@dataclass(frozen=True)
class RunClock:
    """When this run thinks it is, resolved once and passed down.

    Sampled a single time in `main` rather than read where needed. A run that reads
    the clock at several points can stamp a score earlier than the signals it scored,
    and the corpus freshness check would then be comparing two independent samples.
    One value threaded through makes the run self-consistent by construction, and
    keeps `run_collectors` and `run_models` taking injected timestamps -- which is
    what makes them reproducible in a test.
    """

    stamp: str
    run_id: str
    as_of: date | None
    """What `recent-results` treats as today. None means the collector uses the clock,
    which is correct only when its pages come from the live source."""

    @classmethod
    def now(cls) -> RunClock:
        """A run's clock, read once at the start of that run.

        `as_of` is None because a live scan walks backwards from today, and today is
        whatever the collector finds when it looks. The end-to-end test builds a
        RunClock directly with a fixed anchor instead -- see that test for why the
        anchor there is not a placeholder awaiting this method.
        """
        now = datetime.now(UTC).isoformat(timespec="seconds")
        # Colons are legal in the id but awkward in a filename or a URL, and this
        # value ends up in both. Sorting is preserved either way.
        return cls(stamp=now, run_id=f"run-{now.replace(':', '-')}", as_of=None)


class StoreCorpus:
    """Binds the runtime's `Corpus` protocol to the store.

    This adapter exists so that neither side imports the other: the runtime knows
    nothing about SQLite, the store knows nothing about collection ordering, and
    this script -- which already knows about both -- joins them. `check_dependencies.py`
    enforces the half of that which is a real rule.
    """

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def freshness(self, collector_id: str) -> str | None:
        return corpus_freshness(self._conn, collector_id)

    def read(self, collector_id: str, entity_ids: Iterable[str]) -> Any:
        return read_corpus(self._conn, collector_id, entity_ids)

    def write(
        self,
        *,
        run_id: str,
        collector_id: str,
        entity_kind: str,
        asked: Iterable[str],
        values: Mapping[str, Mapping[str, Any]],
        collected_at: str,
    ) -> None:
        write_corpus(
            self._conn,
            run_id=run_id,
            collector_id=collector_id,
            entity_kind=entity_kind,
            asked=asked,
            values=values,
            collected_at=collected_at,
        )


def build_collector_registry(
    pages: Any, clock: RunClock, extra: Iterable[Any] = ()
) -> tuple[CollectorRegistry, RecentResults]:
    """The only place that knows which collectors exist.

    `recent-results` is the same collector wherever its bytes come from -- the same
    scan, the same stopping rule, the same parsing. Only the page source differs, which
    is why that is a parameter rather than a branch inside the collector.

    Where its pages come from and what it treats as today are separate arguments on
    purpose: the first is about the source, the second about the run.

    `extra` exists for collectors that invent their values. Nothing that runs writes
    fabricated rows into the same corpus as collected ones, so the only caller that
    passes anything here is the end-to-end test, where the invented values are the
    point.
    """
    registry = CollectorRegistry()
    for collector in extra:
        registry.register(collector)

    recent_results = RecentResults(pages, as_of=clock.as_of)
    registry.register(recent_results)

    return registry, recent_results


def build_registry(
    provided_paths: frozenset[str] = frozenset(), extra: Iterable[Any] = ()
) -> Registry:
    """The only place that knows which models exist.

    Adding a model is one import and one register() call -- nothing else in the
    system changes.

    `provided_paths` comes from the collector registry. A model declaring a signal
    nothing provides fails here rather than skipping every match in silence.
    """
    registry = Registry(provided_paths=provided_paths)
    registry.register(OVER_UNDER_LEAN)
    registry.register(ODDS_SPREAD)
    registry.register(RECENT_GOALS_TOTAL)
    for model in extra:
        registry.register(model)
    return registry


def acquire_live(conn: Any, say: Any) -> bool:
    """Put canonical matches in the store by asking the schedule source.

    The one step in this pipeline that touches the network, and it runs before the
    slate exists because it produces what the slate is made of.
    """
    run = acquire_window(conn)
    say(f"  acquisition  {run.summary()}")
    if run.failed:
        # Stop rather than continue into an empty slate. Carrying on would
        # produce a run that looks exactly like a quiet week, which is the
        # confusion the schedule_run record exists to prevent -- and printing
        # the reason here is what makes it visible without querying for it.
        say("\n  The schedule source could not be read, so there is no slate.")
        say("  This is a source failure, NOT a window with nothing worth watching.")
        return False
    return True


def run_pipeline(
    *,
    clock: RunClock,
    pages: Any,
    acquire: Any,
    rule: str,
    quiet: bool = False,
    refresh: bool = False,
    extra_collectors: Iterable[Any] = (),
    extra_models: Iterable[Any] = (),
) -> int:
    """Migrate, acquire, collect, score, persist -- the whole run.

    Everything that varies between a live run and the end-to-end test is a parameter,
    and everything below them is shared. That is deliberate: the value of the offline
    test is that it exercises the code a live run executes, so a seam added here for
    convenience quietly reduces what CI covers. A new parameter on this function needs
    a reason.
    """

    def say(*parts: object) -> None:
        if not quiet:
            print(*parts)

    conn = connect()

    applied = list(migrate(conn))
    say(f"  migrations   {len(applied)} applied" if applied else "  migrations   up to date")
    say(f"  run          {clock.run_id} at {clock.stamp}")

    if not acquire(conn, say):
        conn.close()
        return 1

    # The slate is decided before any collector runs, because collectors fan out
    # from it -- a team-keyed collector needs to know which teams are in play.
    slate = assemble_slate(conn, rule=rule)
    say(f"  slate        {len(slate.matches)} matches, "
        f"{len(slate.teams())} teams, {len(slate.leagues())} leagues "
        f"({slate.selection.rule})")

    collectors, recent_results = build_collector_registry(pages, clock, extra_collectors)
    registry = build_registry(collectors.provided_paths(), extra_models)

    # Only what some active model actually declares gets collected. A source
    # nothing consumes is not fetched -- rate limits are real.
    required = {p for m in registry.active() for p in m.model.required_features}
    try:
        collection = run_collectors(
            collectors,
            slate,
            required,
            run_id=clock.run_id,
            started_at=clock.stamp,
            completed_at=clock.stamp,
            corpus=StoreCorpus(conn),
            force=refresh,
        )
    finally:
        # A live scan holds an open connection to the source for its whole walk
        # backwards. Nothing downstream needs it, and leaving it to the garbage
        # collector is how a long-running caller ends up with a socket per run.
        recent_results.close()
    write_collection_run(conn, collection, slate.selection.to_dict())
    say(f"  collection   {collection.summary()}")
    for outcome in collection.outcomes:
        if outcome.reason:
            detail = outcome.reason
        elif outcome.entities_with_data is None:
            detail = "no model declared anything it provides"
        else:
            counts = (
                f"{outcome.entities_with_data} with data, "
                f"{outcome.entities_without_data} without"
            )
            # Spelling out that no request was made is the point of the outcome.
            # Without it a reused run reads exactly like a run that re-fetched.
            detail = (
                f"{counts}, from the stored corpus \u2014 source not contacted"
                if outcome.outcome == "reused"
                else counts
            )
        say(f"               {outcome.collector_id}: {outcome.outcome} \u2014 {detail}")

    # Scored matches are the SLATE, not everything in the store. Live acquisition
    # writes every match the source returned worldwide so that "we asked and nobody
    # carries it" is a recorded fact; scoring all of that would make the selection
    # rule decorative.
    #
    # Signals are folded in before hashing, so a changed signal yields a new
    # snapshot_hash and therefore a new score row.
    snapshots = load_snapshots(
        conn, signals=collection.signals, match_ids=slate.match_ids()
    )
    say(f"  snapshots    {len(snapshots)} assembled from canonical entities")

    register_models(conn, registry)

    run = run_models(
        registry,
        snapshots,
        computed_at=clock.stamp,
        unavailable=collection.unavailable_paths(),
    )
    write_scores(conn, run.scores)
    say(f"  scoring      {run.summary()}")
    for skip in run.skips:
        say(f"               skipped {skip.match_id} / {skip.model_id}: {skip.reason}")

    # Calibration and composition are shown here, but they are NOT persisted -- the
    # caller picks the cohort per request, so these are derived at read time by the API.
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
        value = f"{score.value:5.1f}" if score.value is not None else "    \u2014"
        say(f"    {value}  {match_id}")

    conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "collect from every source regardless of what is already stored. "
            "Without this, a collector whose persisted output is still inside its "
            "declared refresh window and covers the whole slate is not called at "
            "all. Use when you know the source has changed."
        ),
    )
    args = parser.parse_args()

    # There is no offline mode. A run acquires from the schedule source or it
    # produces nothing -- deliberately, so that the thing a person runs and the
    # thing CI exercises cannot drift into being two different systems. CI runs
    # this same pipeline with its inputs supplied; see
    # packages/api/tests/test_end_to_end_offline.py.
    return run_pipeline(
        clock=RunClock.now(),
        pages=LivePages(),
        acquire=acquire_live,
        rule="us-watchable",
        quiet=args.quiet,
        refresh=args.refresh,
    )


if __name__ == "__main__":
    sys.exit(main())
