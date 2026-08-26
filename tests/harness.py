"""How to run the pipeline with nothing fetched.

The pipeline has no offline mode -- a run acquires from the schedule source or
produces nothing. What it has instead is `run_pipeline(...)`, whose inputs are
arguments. This module supplies the captured ones, and it is the ONLY place that
knows how: the end-to-end test and `scripts/check_api_conformance.py` both call it,
so there is one description of "the pipeline, offline" rather than two that must be
kept in step.

Nothing a user runs imports this. It reads `tests/captures/`, which is somebody
else's bytes kept for exactly this purpose, and it registers collectors that invent
their values -- which is why it is here and not anywhere a real run could reach it.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

OFFLINE_STAMP = "2026-08-14T04:00:00+00:00"
"""This harness's instant, and its run identifier's basis.

NOT a placeholder awaiting the clock. An offline run is a REPRODUCTION, not a
simulation of today: two runs over unchanged inputs must produce identical rows,
identical timestamps and identical run ids, because the end-to-end test compares
them. Making this clock-driven would end that, and would break `recent-results`
outright -- see OFFLINE_AS_OF below."""

OFFLINE_RUN_ID = "offline-e2e"
"""Constant on purpose, so repeated offline runs are the SAME run repeated rather
than two runs. A live run derives a distinct id per run instead."""

OFFLINE_AS_OF = date(2026, 8, 14)
"""What "now" means to `recent-results` here.

Pinned rather than read from the clock, so that an offline run is reproducible: the
captured pages in `tests/captures/goal-com/results/` were taken walking back from
this date, and a scan starting anywhere else would drift off the end of them as the
real date moved.

Like OFFLINE_STAMP, this is not waiting to be replaced by `date.today()`. Doing that
would make the scan walk backwards from the present through pages that do not exist,
and report an absence of results that is an artefact of the anchor rather than a fact
about any source -- which is exactly the failure the collector tier is built to
avoid."""


def load_pipeline() -> Any:
    """Import scripts/pipeline.py, which is a script rather than a package."""
    if "_xfun_pipeline" in sys.modules:
        return sys.modules["_xfun_pipeline"]
    spec = importlib.util.spec_from_file_location(
        "_xfun_pipeline", ROOT / "scripts" / "pipeline.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["_xfun_pipeline"] = module
    spec.loader.exec_module(module)
    return module


def ingest_fixtures(conn: Any, say: Any) -> bool:
    """How canonical matches reach the store when nobody is fetching them.

    Stands where `acquire_live` stands in a real run. The authored snapshots carry no
    broadcast availability, which is why the slate rule is `league-allowlist` rather
    than `us-watchable` -- the latter would correctly admit none of them.
    """
    from xfun_ingestion import fixture_payloads, ingest

    result = ingest(conn, fixture_payloads())
    say(f"  ingestion    {result.summary()}")
    return True


def offline_arguments(pipeline: Any, *, quiet: bool = True) -> dict[str, Any]:
    """The four seams a live run gets from elsewhere, plus the test-only registrations.

    Everything below these arguments is the code a live run executes. That is the
    point of the harness: a check that took a different route through the system
    would not be checking the pipeline.
    """
    from xfun_collector_fixture_signals import fixture_collectors
    from xfun_collector_recent_results import CapturedPages
    from xfun_model_social_buzz import MODEL as SOCIAL_BUZZ
    from xfun_runtime.paths import captures_dir

    return {
        "clock": pipeline.RunClock(
            stamp=OFFLINE_STAMP, run_id=OFFLINE_RUN_ID, as_of=OFFLINE_AS_OF
        ),
        "pages": CapturedPages(captures_dir() / "goal-com" / "results"),
        "acquire": ingest_fixtures,
        "rule": "league-allowlist",
        "quiet": quiet,
        # Invented values, and a model that reads them. Registered only here, so that
        # nothing a person runs writes a fabricated row into the same corpus as a
        # collected one -- the corpus cannot record which kind a value is.
        "extra_collectors": fixture_collectors(),
        "extra_models": (SOCIAL_BUZZ,),
    }


def run_offline(*, quiet: bool = True) -> int:
    """Run the whole pipeline against captured inputs. Returns its exit code."""
    pipeline = load_pipeline()
    return pipeline.run_pipeline(**offline_arguments(pipeline, quiet=quiet))
