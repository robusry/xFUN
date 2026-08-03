"""Acquiring a window, and the failure that must not look like a quiet week.

Every test here is really about one confusion. An empty slate can mean the source
answered and nothing is watchable, or that the source could not be reached. The
leagues in scope go between seasons, so a genuinely empty fortnight is normal --
which is exactly what makes a broken source easy to miss.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from xfun_ingestion import assemble_slate
from xfun_ingestion.schedule import (
    SOURCE_ID,
    ScheduleSourceError,
    acquire_window,
    fetch_window,
    load_rights,
    parse_schedule,
    schedule_url,
    window_dates,
)
from xfun_runtime.paths import fixtures_dir
from xfun_store import connect, latest_schedule_run, migrate, read_availability

DENSE = fixtures_dir() / "schedule" / "2026-08-22-dense.html"
MALFORMED = fixtures_dir() / "schedule" / "malformed-state.html"

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = connect(":memory:")
    list(migrate(connection))
    return connection


@pytest.fixture
def rights():
    return load_rights()


@pytest.fixture
def captured():
    return parse_schedule(DENSE.read_text(encoding="utf-8"))


def _transport(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# --- the window ----------------------------------------------------------


def test_window_covers_both_ends() -> None:
    days = window_dates(NOW, 10)

    assert days[0].isoformat() == "2026-08-20"
    assert days[-1].isoformat() == "2026-08-30"


def test_window_includes_the_final_evening() -> None:
    """A ten-day window from midday spans eleven dates. Fetching the extra one is
    cheaper than missing a match on the last night."""
    assert len(window_dates(NOW, 10)) == 11


def test_url_is_date_addressed() -> None:
    assert schedule_url(NOW.date()) == "https://www.goal.com/en-us/fixtures/2026-08-20"


# --- a successful acquisition -------------------------------------------


def test_only_watchable_matches_are_stored(conn, rights, captured) -> None:
    """The source lists every competition on earth. Storing all of it would scope
    the store to the source rather than to the product, and every reader downstream
    would need to remember the same filter."""
    run = acquire_window(conn, now=NOW, matches=captured, rights=rights)

    assert not run.failed
    assert run.matches_seen == len(captured)
    stored = conn.execute("SELECT COUNT(*) FROM match").fetchone()[0]
    assert stored == run.matches_watchable < run.matches_seen


def test_every_stored_match_has_a_known_broadcaster(conn, rights, captured) -> None:
    acquire_window(conn, now=NOW, matches=captured, rights=rights)

    statuses = {
        r["status"] for r in conn.execute("SELECT DISTINCT status FROM match_availability")
    }
    assert statuses == {"known"}


def test_providers_come_from_the_source_where_it_has_them(conn, rights, captured) -> None:
    acquire_window(conn, now=NOW, matches=captured, rights=rights)

    row = conn.execute(
        "SELECT match_id FROM match_availability WHERE resolved_from = 'source' LIMIT 1"
    ).fetchone()
    assert row is not None
    assert read_availability(conn, row["match_id"]).providers


def test_the_rights_table_fills_what_the_source_leaves_empty(conn, rights, captured) -> None:
    """MLS NEXT Pro is in the capture with no providers, and is exactly what the
    table exists for."""
    acquire_window(conn, now=NOW, matches=captured, rights=rights)

    row = conn.execute(
        "SELECT match_id FROM match_availability WHERE resolved_from = 'rights-table' LIMIT 1"
    ).fetchone()
    assert row is not None
    assert "OneFootball" in read_availability(conn, row["match_id"]).providers


def test_a_league_neither_answers_for_is_absent(conn, rights, captured) -> None:
    """Liga MX: the source names nobody and its rights are held per club, so no
    league-wide entry can be written. It never reaches the store."""
    assert any(m.competition_name == "Liga MX" for m in captured)

    acquire_window(conn, now=NOW, matches=captured, rights=rights)

    rows = conn.execute(
        "SELECT match_id FROM match WHERE league_id = 'mexico-liga-mx'"
    ).fetchall()
    assert rows == []


def test_the_run_is_recorded_as_ok(conn, rights, captured) -> None:
    acquire_window(conn, now=NOW, matches=captured, rights=rights)

    run = latest_schedule_run(conn)
    assert run is not None
    assert run.status == "ok"
    assert run.reason is None
    assert run.source_id == SOURCE_ID


def test_watchable_is_counted_separately_from_seen(conn, rights, captured) -> None:
    """A source that answered fully but named no providers, and a source that
    returned nothing, both produce an empty slate. These two counts separate them."""
    run = acquire_window(conn, now=NOW, matches=captured, rights=rights)

    assert run.matches_seen > run.matches_watchable > 0


# --- failure -------------------------------------------------------------


def test_an_unreachable_source_is_recorded_not_raised(conn, rights) -> None:
    """A caller that must catch an exception to notice will eventually forget to,
    and the empty slate that follows looks like an ordinary quiet week."""

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with _transport(down) as client, pytest.raises(ScheduleSourceError, match="could not reach"):
        fetch_window(NOW, 1, client=client)


def test_a_refusal_says_not_to_work_around_it(conn) -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="no")

    with _transport(refused) as client, pytest.raises(ScheduleSourceError, match="work around"):
        fetch_window(NOW, 1, client=client)


def test_a_server_error_fails_the_window(conn) -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="later")

    with _transport(broken) as client, pytest.raises(ScheduleSourceError, match="503"):
        fetch_window(NOW, 1, client=client)


def test_a_source_that_changed_shape_fails_the_window(conn) -> None:
    body = MALFORMED.read_text(encoding="utf-8")

    def changed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    with _transport(changed) as client, pytest.raises(ScheduleSourceError, match="liveScores"):
        fetch_window(NOW, 1, client=client)


def test_a_partial_window_is_not_accepted(conn) -> None:
    """A missing Saturday looks like a thin week, and the caller has no way to tell
    that a date was silently dropped."""
    good = DENSE.read_text(encoding="utf-8")
    seen: list[str] = []

    def flaky(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if len(seen) == 2:
            return httpx.Response(500, text="")
        return httpx.Response(200, text=good)

    with _transport(flaky) as client, pytest.raises(ScheduleSourceError):
        fetch_window(NOW, 3, client=client)


# --- failure does not masquerade as an empty window ----------------------


def _unreachable(_start, _days):
    raise ScheduleSourceError("could not reach the source: connection refused")


def test_failure_and_a_quiet_week_are_distinguishable(conn, rights) -> None:
    quiet = acquire_window(conn, now=NOW, matches=(), rights=rights)
    assert not quiet.failed
    assert quiet.matches_seen == 0

    failed = acquire_window(conn, now=NOW, rights=rights, fetch=_unreachable)

    assert failed.failed
    assert failed.reason

    # Both left the same empty slate; only the record separates them.
    assert assemble_slate(conn, rule="us-watchable", now=NOW).matches == ()


def test_a_failed_run_does_not_claim_the_window_was_empty(conn, rights, captured) -> None:
    """Matches from an earlier successful run stay in the store. The failure must
    still be recorded as a failure rather than inferred away."""
    acquire_window(conn, now=NOW, matches=captured, rights=rights)
    assert conn.execute("SELECT COUNT(*) FROM match").fetchone()[0] > 0

    run = acquire_window(
        conn, now=NOW + timedelta(hours=1), rights=rights, fetch=_unreachable
    )

    assert run.failed
    assert latest_schedule_run(conn).status == "failed"


def test_a_failure_is_returned_rather_than_raised(conn, rights) -> None:
    """No exception escapes. A caller that had to catch one would eventually forget,
    and the empty slate that followed would read as an ordinary quiet week."""
    run = acquire_window(conn, now=NOW, rights=rights, fetch=_unreachable)

    assert run.failed
    assert "could not reach" in run.reason


def test_a_failed_run_must_say_why(conn, rights) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO schedule_run (run_id, source_id, status, reason, "
            "window_start_utc, window_end_utc, ran_at) "
            "VALUES ('r', 'goal.com', 'failed', NULL, 'a', 'b', datetime('now'))"
        )
