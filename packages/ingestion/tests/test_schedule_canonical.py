"""Deriving canonical identifiers, and writing entities that converge.

Two properties matter here and both fail quietly if they break.

The first is that the identifier is a function of the match and nothing else, so a
second run over an overlapping window updates rows instead of adding them. A
pipeline that duplicates its matches still produces plausible output, and the only
symptom is a slowly growing table.

The second is the competition collision. Ids derived from a competition name alone
would merge the English and Kazakh `Premier League` into one league holding both
sets of clubs, and every count in the system would still add up.
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from jsonschema import Draft202012Validator
from xfun_ingestion import ingest
from xfun_ingestion.schedule import (
    CanonicalIdError,
    canonical_payload,
    league_id,
    match_id,
    parse_schedule,
    slugify,
    team_id,
)
from xfun_runtime.paths import fixtures_dir, schemas_dir
from xfun_store import connect, migrate

DENSE = fixtures_dir() / "schedule" / "2026-08-22-dense.html"

EPL_ENGLAND = "2kwbbcootiqqgmrzs6o5inle5"
PL_KAZAKHSTAN = "9ikchyu9fb8bvx0s673jofj6s"


@pytest.fixture
def matches():
    return parse_schedule(DENSE.read_text(encoding="utf-8"))


@pytest.fixture
def snapshot_validator() -> Draft202012Validator:
    schema = json.loads((schemas_dir() / "match-snapshot.json").read_text())
    return Draft202012Validator(schema)


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = connect(":memory:")
    # migrate() is a generator yielding each migration applied; it does nothing
    # until consumed.
    list(migrate(connection))
    return connection


# --- slugs ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Arsenal", "arsenal"),
        ("Manchester United", "manchester-united"),
        ("St. Louis City 2", "st-louis-city-2"),
        ("Red Bull New York  II", "red-bull-new-york-ii"),
        ("Atlético Ottawa", "atletico-ottawa"),
        ("Queens Park Rangers", "queens-park-rangers"),
        ("  leading and trailing  ", "leading-and-trailing"),
    ],
)
def test_slugify(raw: str, expected: str) -> None:
    assert slugify(raw) == expected


def test_accents_fold_rather_than_drop() -> None:
    """`atltico` would be a different club from `atletico` on the next run if the
    source ever wrote the name without its accent."""
    assert slugify("Atlético") == slugify("Atletico")


def test_numerals_are_kept() -> None:
    """A reserve side is not its first team, and dropping the digit merges them."""
    assert slugify("Columbus Crew 2") != slugify("Columbus Crew")


@pytest.mark.parametrize("raw", ["", "   ", "!!!", "—"])
def test_unusable_names_raise(raw: str) -> None:
    with pytest.raises(CanonicalIdError):
        slugify(raw)


def test_teams_are_keyed_by_name_alone() -> None:
    assert team_id("Hull City") == "hull-city"


def test_clubs_sharing_a_name_across_countries_collide() -> None:
    """A KNOWN limitation, asserted so it is a recorded decision rather than a
    surprise. The source attaches a country to competitions and not to teams, so
    there is nothing here to disambiguate with. Design D9 accepts this; deriving a
    country from the first competition a club was seen in would be worse, since it
    would mislabel any club first seen in a continental competition."""
    assert team_id("River Plate") == team_id("River Plate")


# --- the collision -------------------------------------------------------


def test_country_separates_leagues_sharing_a_name() -> None:
    assert league_id("Premier League", "England") != league_id(
        "Premier League", "Kazakhstan"
    )


def test_league_id_shape() -> None:
    assert league_id("Premier League", "England") == "england-premier-league"
    assert league_id("Liga MX", "Mexico") == "mexico-liga-mx"


def test_two_premier_leagues_stay_apart_end_to_end(matches) -> None:
    payloads = [canonical_payload(m) for m in matches]
    by_source = {m.competition_id: p for m, p in zip(matches, payloads, strict=True)}

    assert (
        by_source[EPL_ENGLAND]["league"]["id"]
        != by_source[PL_KAZAKHSTAN]["league"]["id"]
    )


# --- match ids -----------------------------------------------------------


def test_match_id_shape() -> None:
    assert (
        match_id("england-premier-league", "2026-08-22T11:30:00.000Z", "hull-city", "man-utd")
        == "england-premier-league-2026-08-22-hull-city-man-utd"
    )


def test_match_id_ignores_time_of_day() -> None:
    """A kickoff moved by an hour is the same match, not a second one."""
    early = match_id("l", "2026-08-22T11:30:00.000Z", "h", "a")
    late = match_id("l", "2026-08-22T19:00:00.000Z", "h", "a")

    assert early == late


def test_match_id_rejects_an_unreadable_kickoff() -> None:
    with pytest.raises(CanonicalIdError):
        match_id("l", "next tuesday", "h", "a")


# --- payloads ------------------------------------------------------------


def test_payloads_conform_to_the_snapshot_schema(matches, snapshot_validator) -> None:
    for match in matches:
        errors = list(snapshot_validator.iter_errors(canonical_payload(match)))
        assert not errors, [e.message for e in errors]


def test_payloads_carry_nothing_a_model_reads(matches) -> None:
    """Acquisition establishes matches and where to watch them. Everything a model
    consumes belongs to another tier, and its absence here is why nothing scores."""
    for match in matches:
        payload = canonical_payload(match)
        assert "odds" not in payload
        assert "form" not in payload
        assert "table" not in payload
        assert "signals" not in payload


def test_availability_is_not_in_the_snapshot(matches) -> None:
    """Design D6: stored beside the match, so no model can score by broadcaster."""
    for match in matches:
        assert "availability" not in canonical_payload(match)


def test_ids_are_a_function_of_the_match_alone(matches) -> None:
    first = [canonical_payload(m) for m in matches]
    second = [canonical_payload(m) for m in matches]

    assert first == second


# --- convergence ---------------------------------------------------------


def _counts(conn: sqlite3.Connection) -> tuple[int, int, int]:
    return (
        conn.execute("SELECT COUNT(*) FROM match").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM team").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM league").fetchone()[0],
    )


def test_writing_a_parsed_response_creates_entities(conn, matches) -> None:
    ingest(conn, [canonical_payload(m) for m in matches], source_id="goal.com")

    match_count, team_count, league_count = _counts(conn)
    assert match_count == len(matches)
    assert team_count > 0
    assert league_count == len({m.competition_id for m in matches})


def test_re_running_converges_rather_than_duplicating(conn, matches) -> None:
    payloads = [canonical_payload(m) for m in matches]

    ingest(conn, payloads, source_id="goal.com")
    after_first = _counts(conn)
    ingest(conn, payloads, source_id="goal.com")
    after_second = _counts(conn)

    assert after_first == after_second


def test_an_overlapping_window_does_not_duplicate(conn, matches) -> None:
    """The realistic case: runs overlap because the window slides continuously."""
    payloads = [canonical_payload(m) for m in matches]

    ingest(conn, payloads[: len(payloads) // 2], source_id="goal.com")
    ingest(conn, payloads, source_id="goal.com")

    assert _counts(conn)[0] == len(payloads)
