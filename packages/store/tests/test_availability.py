"""Storing where a match can be watched.

The property under test throughout is that the system cannot end up asserting a
provider it does not have. Every other failure here is visible; that one is not,
because a wrong provider looks exactly like a right one until somebody tunes in.
"""

from __future__ import annotations

import sqlite3

import pytest
from xfun_store import (
    MatchAvailability,
    connect,
    migrate,
    read_availability,
    read_availability_map,
    write_availability,
    write_snapshot_payload,
)

MATCH = "usa-mls-next-pro-2026-08-08-portland-timbers-2-los-angeles-fc-ii"
OTHER = "england-premier-league-2026-08-22-hull-city-manchester-united"


def _snapshot(match_id: str) -> dict:
    return {
        "match_id": match_id,
        "league": {"id": "usa-mls-next-pro", "name": "MLS NEXT Pro"},
        "kickoff_utc": "2026-08-08T20:00:00.000Z",
        "home_team": {"id": "home", "name": "Home"},
        "away_team": {"id": "away", "name": "Away"},
    }


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = connect(":memory:")
    list(migrate(connection))
    for match_id in (MATCH, OTHER):
        write_snapshot_payload(connection, _snapshot(match_id))
    return connection


# --- round trip ----------------------------------------------------------


def test_known_availability_round_trips(conn) -> None:
    write_availability(
        conn,
        MATCH,
        MatchAvailability("known", ("OneFootball", "MLSNEXTPro.com"), "rights-table"),
    )

    stored = read_availability(conn, MATCH)
    assert stored.known
    assert stored.providers == ("OneFootball", "MLSNEXTPro.com")
    assert stored.resolved_from == "rights-table"


def test_provider_order_is_preserved(conn) -> None:
    write_availability(
        conn, MATCH, MatchAvailability("known", ("NBC", "Peacock", "USA Network"), "source")
    )

    assert read_availability(conn, MATCH).providers == ("NBC", "Peacock", "USA Network")


def test_unknown_round_trips(conn) -> None:
    write_availability(conn, MATCH, MatchAvailability("unknown"))

    stored = read_availability(conn, MATCH)
    assert not stored.known
    assert stored.providers == ()
    assert stored.resolved_from is None


# --- absence and unknown mean the same thing to a reader -----------------


def test_a_match_with_no_row_is_unknown(conn) -> None:
    assert read_availability(conn, MATCH).status == "unknown"


def test_an_unrecognised_match_is_unknown(conn) -> None:
    assert read_availability(conn, "no-such-match").status == "unknown"


# --- what cannot be stored ----------------------------------------------


def test_known_with_no_providers_is_refused(conn) -> None:
    """It would read as "we checked and it is on nothing", which is a stronger and
    different claim than "unknown"."""
    with pytest.raises(ValueError, match="names no provider"):
        write_availability(conn, MATCH, MatchAvailability("known", (), "source"))


def test_the_database_refuses_a_known_row_with_no_provenance(conn) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO match_availability (match_id, status, resolved_from, resolved_at) "
            "VALUES (?, 'known', NULL, datetime('now'))",
            (MATCH,),
        )


def test_the_database_refuses_an_invented_status(conn) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO match_availability (match_id, status, resolved_from, resolved_at) "
            "VALUES (?, 'probably', 'source', datetime('now'))",
            (MATCH,),
        )


# --- rewriting -----------------------------------------------------------


def test_rewriting_replaces_rather_than_accumulates(conn) -> None:
    """Unlike a score, this is not a historical record. A provider that changed is
    wrong now, not superseded."""
    write_availability(conn, MATCH, MatchAvailability("known", ("Old Network",), "source"))
    write_availability(conn, MATCH, MatchAvailability("known", ("New Network",), "source"))

    assert read_availability(conn, MATCH).providers == ("New Network",)
    count = conn.execute(
        "SELECT COUNT(*) FROM match_provider WHERE match_id = ?", (MATCH,)
    ).fetchone()[0]
    assert count == 1


def test_narrowing_to_unknown_drops_providers(conn) -> None:
    write_availability(conn, MATCH, MatchAvailability("known", ("Some Network",), "source"))
    write_availability(conn, MATCH, MatchAvailability("unknown"))

    assert read_availability(conn, MATCH).providers == ()


# --- reading many --------------------------------------------------------


def test_reading_many_at_once(conn) -> None:
    write_availability(conn, MATCH, MatchAvailability("known", ("OneFootball",), "rights-table"))
    write_availability(conn, OTHER, MatchAvailability("known", ("NBC", "Peacock"), "source"))

    found = read_availability_map(conn, [MATCH, OTHER])

    assert found[MATCH].providers == ("OneFootball",)
    assert found[OTHER].providers == ("NBC", "Peacock")


def test_matches_with_no_answer_are_absent_from_the_map(conn) -> None:
    write_availability(conn, MATCH, MatchAvailability("known", ("OneFootball",), "rights-table"))

    found = read_availability_map(conn, [MATCH, OTHER])

    assert MATCH in found
    assert OTHER not in found


def test_reading_no_matches_asks_nothing(conn) -> None:
    assert read_availability_map(conn, []) == {}


def test_reading_every_match(conn) -> None:
    write_availability(conn, MATCH, MatchAvailability("known", ("OneFootball",), "rights-table"))

    assert set(read_availability_map(conn)) == {MATCH}


# --- the wire shape ------------------------------------------------------


def test_payload_matches_the_contract_shape() -> None:
    payload = MatchAvailability("known", ("NBC",), "source").to_payload()

    assert payload == {"status": "known", "providers": ["NBC"]}


def test_provenance_is_not_exposed_to_clients() -> None:
    """Which of the two steps answered is for whoever maintains the data. A client
    branching on it would be wrong: the rights table is the more accurate of the
    two where it applies, not a lesser answer."""
    assert "resolved_from" not in MatchAvailability("known", ("NBC",), "source").to_payload()
