"""Which matches reach the slate, under each rule.

`us-watchable` is a hard filter, so every boundary here decides whether a real match
appears in the product at all. The two that matter most are the ones that look like
each other: a match nobody has announced a broadcaster for, and a match nobody
carries. Both are excluded, and the window is what makes that defensible -- inside
ten days the first case has largely resolved itself.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from jsonschema import Draft202012Validator
from xfun_ingestion import UnknownSelectionRule, assemble_slate
from xfun_runtime.paths import schemas_dir
from xfun_store import (
    MatchAvailability,
    connect,
    migrate,
    write_availability,
    write_snapshot_payload,
)

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def _add_match(
    conn: sqlite3.Connection,
    match_id: str,
    *,
    kickoff: datetime,
    league: str = "usa-usl-championship",
    providers: tuple[str, ...] = (),
    availability: bool = True,
) -> None:
    write_snapshot_payload(
        conn,
        {
            "match_id": match_id,
            "league": {"id": league, "name": league.replace("-", " ").title()},
            "kickoff_utc": _iso(kickoff),
            "home_team": {"id": f"{match_id}-h", "name": "Home"},
            "away_team": {"id": f"{match_id}-a", "name": "Away"},
        },
    )
    if not availability:
        return
    write_availability(
        conn,
        match_id,
        MatchAvailability("known", providers, "source")
        if providers
        else MatchAvailability("unknown"),
    )


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = connect(":memory:")
    list(migrate(connection))
    return connection


@pytest.fixture
def slate_validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads((schemas_dir() / "slate.json").read_text()))


# --- the four boundary cases from the spec -------------------------------


def test_known_provider_inside_the_window_is_admitted(conn) -> None:
    _add_match(conn, "inside-known", kickoff=NOW + timedelta(days=3), providers=("ESPN+",))

    slate = assemble_slate(conn, rule="us-watchable", now=NOW)

    assert slate.match_ids() == ("inside-known",)


def test_no_provider_inside_the_window_is_excluded(conn) -> None:
    _add_match(conn, "inside-unknown", kickoff=NOW + timedelta(days=3))

    slate = assemble_slate(conn, rule="us-watchable", now=NOW)

    assert slate.matches == ()


def test_known_provider_beyond_the_window_is_excluded(conn) -> None:
    _add_match(conn, "outside-known", kickoff=NOW + timedelta(days=14), providers=("ESPN+",))

    slate = assemble_slate(conn, rule="us-watchable", now=NOW)

    assert slate.matches == ()


def test_a_window_with_nothing_watchable_is_an_empty_slate(conn) -> None:
    """Empty, and successfully so. The run record is what separates this from a
    source that could not be reached."""
    _add_match(conn, "unknown-a", kickoff=NOW + timedelta(days=1))
    _add_match(conn, "unknown-b", kickoff=NOW + timedelta(days=2))

    slate = assemble_slate(conn, rule="us-watchable", now=NOW)

    assert slate.matches == ()
    assert slate.selection.rule == "us-watchable"


# --- window edges --------------------------------------------------------


def test_a_match_already_kicked_off_is_excluded(conn) -> None:
    _add_match(conn, "past", kickoff=NOW - timedelta(hours=2), providers=("ESPN+",))

    assert assemble_slate(conn, rule="us-watchable", now=NOW).matches == ()


def test_the_far_edge_is_exclusive(conn) -> None:
    _add_match(conn, "day-ten", kickoff=NOW + timedelta(days=10), providers=("ESPN+",))
    _add_match(
        conn, "just-inside", kickoff=NOW + timedelta(days=10, hours=-1), providers=("ESPN+",)
    )

    assert assemble_slate(conn, rule="us-watchable", now=NOW).match_ids() == ("just-inside",)


def test_the_window_moves_with_the_run(conn) -> None:
    """The window is measured from the run, not from a fixed date, because "what
    can I watch soon" moves continuously."""
    _add_match(conn, "later", kickoff=NOW + timedelta(days=12), providers=("ESPN+",))

    assert assemble_slate(conn, rule="us-watchable", now=NOW).matches == ()
    assert assemble_slate(
        conn, rule="us-watchable", now=NOW + timedelta(days=5)
    ).match_ids() == ("later",)


# --- absence and explicit unknown are the same answer --------------------


def test_a_match_with_no_availability_row_is_not_watchable(conn) -> None:
    _add_match(conn, "never-asked", kickoff=NOW + timedelta(days=2), availability=False)

    assert assemble_slate(conn, rule="us-watchable", now=NOW).matches == ()


def test_a_match_recorded_unknown_is_not_watchable(conn) -> None:
    _add_match(conn, "asked-no-answer", kickoff=NOW + timedelta(days=2))

    assert assemble_slate(conn, rule="us-watchable", now=NOW).matches == ()


# --- what gets recorded --------------------------------------------------


def test_the_rule_and_window_are_recorded(conn) -> None:
    _add_match(conn, "m", kickoff=NOW + timedelta(days=1), providers=("ESPN+",))

    selection = assemble_slate(conn, rule="us-watchable", now=NOW).selection

    assert selection.rule == "us-watchable"
    assert selection.window_start_utc == _iso(NOW)
    assert selection.window_end_utc == _iso(NOW + timedelta(days=10))


def test_leagues_are_recorded_as_an_outcome(conn) -> None:
    _add_match(conn, "a", kickoff=NOW + timedelta(days=1), league="usa-mls-next-pro",
               providers=("OneFootball",))
    _add_match(conn, "b", kickoff=NOW + timedelta(days=2), league="usa-usl-championship",
               providers=("ESPN+",))

    selection = assemble_slate(conn, rule="us-watchable", now=NOW).selection

    assert selection.leagues == ("usa-mls-next-pro", "usa-usl-championship")


def test_the_slate_conforms_to_its_schema(conn, slate_validator) -> None:
    _add_match(conn, "m", kickoff=NOW + timedelta(days=1), providers=("ESPN+", "Fubo"))

    slate = assemble_slate(conn, rule="us-watchable", now=NOW)

    errors = list(slate_validator.iter_errors(slate.to_dict()))
    assert not errors, [e.message for e in errors]


# --- the older rule stays reachable --------------------------------------


def test_league_allowlist_ignores_availability(conn) -> None:
    """What the fixture path relies on. Fixture snapshots carry no availability, so
    `us-watchable` would correctly admit none of them and a fresh clone would show
    an empty slate."""
    _add_match(conn, "no-availability", kickoff=NOW + timedelta(days=1), availability=False)

    slate = assemble_slate(conn, rule="league-allowlist")

    assert slate.match_ids() == ("no-availability",)
    assert slate.selection.rule == "league-allowlist"


def test_league_allowlist_is_still_the_default(conn) -> None:
    _add_match(conn, "m", kickoff=NOW + timedelta(days=1), availability=False)

    assert assemble_slate(conn).selection.rule == "league-allowlist"


def test_an_unrecorded_rule_is_refused(conn) -> None:
    """The schema admits two values. A slate built under a third could not be read
    back by anything downstream."""
    with pytest.raises(UnknownSelectionRule, match="slate.json"):
        assemble_slate(conn, rule="whatever-looks-good")
