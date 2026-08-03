"""Acquiring a window: fetch, resolve providers, write, record.

The order matters and is not arbitrary.

Providers are resolved for every match the source returned, but only the watchable
ones are stored. The source lists every competition on earth; the product is what a
US viewer can watch. Scoping the store to the product rather than to the source is
what keeps every reader downstream -- pipeline, API, web page -- from having to
remember the same filter independently.

"We asked and nobody carries it" survives as a run-level count rather than a
per-match row, which is the granularity the question is actually asked at.

The run record is written last and always, including when the fetch failed. A run
that fails silently leaves an empty slate that reads exactly like a quiet week.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from xfun_store import (
    MatchAvailability,
    ScheduleRun,
    write_availability,
    write_schedule_run,
    write_snapshot_payload,
)

from ..slate import WATCHABLE_WINDOW_DAYS
from .canonical import CanonicalIdError, canonical_payload
from .parse import SourceMatch
from .rights import RightsTable, load_rights, resolve_providers
from .source import SOURCE_ID, ScheduleSourceError, fetch_window

__all__ = ["Fetcher", "acquire_window", "store_matches"]

Fetcher = Callable[[datetime, int], Sequence[SourceMatch]]
"""Fetches every match in a window. `fetch_window` is the real one.

Exists as an injectable seam so the failure paths can be exercised without the
network. Patching the module attribute would not work -- `acquire` binds the name at
import -- and a test that silently reached the live source would be both slow and
dependent on somebody else's uptime."""


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def store_matches(
    conn: sqlite3.Connection,
    matches: Sequence[SourceMatch],
    rights: RightsTable,
) -> tuple[int, int]:
    """Write the watchable matches. Returns (seen, watchable).

    **Only matches with a known US broadcaster become canonical entities.** The
    source lists every competition in the world -- a live run saw 2005 matches
    across 11 dates, of which 164 were watchable in the US. Storing the other 1841
    would scope the store to the source rather than to the product, and every reader
    downstream would then need to remember to filter: the pipeline, the API, and the
    web page each independently, with the failure mode being a page of Norwegian
    third-division fixtures nobody in the US can watch.

    "We asked and nobody carries it" is still recorded, at the run level rather than
    per match -- `matches_seen` against `matches_watchable` on `schedule_run`. That
    answers the question the record exists for, which is whether a thin slate came
    from a thin week or a broken source.

    *Cost accepted:* a match stored as watchable that later loses its US listing
    keeps its stored providers, because the update path only visits matches that are
    watchable now. The window slides continuously and listings are added far more
    often than withdrawn, so this decays in the harmless direction.

    A match whose name cannot be reduced to an identifier is skipped rather than
    aborting the run. One unparseable club name should not cost a whole window.
    """
    seen = 0
    watchable = 0

    for match in matches:
        try:
            payload = canonical_payload(match)
        except CanonicalIdError:
            continue

        seen += 1
        availability = resolve_providers(
            match.providers, payload["league"]["id"], rights
        )
        if not availability.known:
            continue

        write_snapshot_payload(conn, payload)
        write_availability(
            conn,
            payload["match_id"],
            MatchAvailability(
                status=availability.status,
                providers=availability.providers,
                resolved_from=availability.resolved_from,
            ),
        )
        watchable += 1

    return seen, watchable


def acquire_window(
    conn: sqlite3.Connection,
    *,
    now: datetime | None = None,
    days: int = WATCHABLE_WINDOW_DAYS,
    rights: RightsTable | None = None,
    matches: Sequence[SourceMatch] | None = None,
    fetch: Fetcher | None = None,
) -> ScheduleRun:
    """Acquire the upcoming window and record what happened.

    Never raises for a source problem. The failure is recorded and returned, because
    a caller that has to catch an exception to notice will eventually forget to, and
    the resulting empty slate is indistinguishable from an ordinary quiet week.

    `matches` bypasses the fetch entirely, for replaying a capture. `fetch` replaces
    it, which is how the failure paths are exercised without the network -- an
    injected seam rather than a patched module attribute, so that a test cannot
    reach the real source by accident.
    """
    start = now or datetime.now(UTC)
    window_start = _iso(start)
    # Derived exactly as the slate rule derives it, so the record and the selection
    # always describe the same interval.
    window_end = _iso(start + timedelta(days=days))

    if rights is None:
        rights = load_rights()

    try:
        if matches is not None:
            found = tuple(matches)
        else:
            found = tuple((fetch or fetch_window)(start, days))
    except ScheduleSourceError as exc:
        run = ScheduleRun.failure(SOURCE_ID, window_start, window_end, str(exc))
        write_schedule_run(conn, run)
        conn.commit()
        return run

    seen, watchable = store_matches(conn, found, rights)
    run = ScheduleRun.ok(
        SOURCE_ID,
        window_start,
        window_end,
        matches_seen=seen,
        matches_watchable=watchable,
    )
    write_schedule_run(conn, run)
    conn.commit()
    return run
