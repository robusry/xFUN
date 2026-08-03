"""Parsing a schedule page, against captured responses.

These run on the golden captures in `contracts/fixtures/schedule/`, so they exercise
the source's real shape without the network. That matters more here than for an
authored fixture: the thing under test is somebody else's page structure, and the
only honest way to test a parser for it is against bytes that structure actually
produced.

The case worth reading first is the competition collision. Two different leagues
share the display name `Premier League` in the same response, and a parser that
matched on name would merge Arsenal with Kairat Almaty while every test about
counts and providers still passed.
"""

from __future__ import annotations

import pytest
from xfun_ingestion.schedule import (
    ScheduleParseError,
    competition_groups,
    parse_schedule,
    sports_events,
)
from xfun_runtime.paths import fixtures_dir

SCHEDULE_FIXTURES = fixtures_dir() / "schedule"

EPL_ENGLAND = "2kwbbcootiqqgmrzs6o5inle5"
PL_KAZAKHSTAN = "9ikchyu9fb8bvx0s673jofj6s"
MLS_NEXT_PRO = "5qmjkpvi92vrzdcb2knassjkk"
LIGA_MX = "2hsidwomhjsaaytdy9u5niyi4"


def _read(name: str) -> str:
    return (SCHEDULE_FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def dense() -> str:
    return _read("2026-08-22-dense.html")


@pytest.fixture
def sparse() -> str:
    return _read("2026-08-12-sparse.html")


@pytest.fixture
def malformed() -> str:
    return _read("malformed-state.html")


# --- the two parsers, separately -----------------------------------------


def test_json_ld_yields_sports_events(dense: str) -> None:
    events = sports_events(dense)

    assert events, "capture should carry schema.org blocks"
    assert all(e["@type"] == "SportsEvent" for e in events)
    assert all(e.get("startDate") for e in events)
    assert all((e.get("homeTeam") or {}).get("name") for e in events)


def test_json_ld_carries_no_competition(dense: str) -> None:
    """The reason both parsers exist rather than just the standard one."""
    for event in sports_events(dense):
        assert "competition" not in event
        assert "tvChannels" not in event


def test_page_state_groups_carry_a_competition_id(dense: str) -> None:
    groups = competition_groups(dense)

    assert groups
    for group in groups:
        competition = group["competition"]
        assert competition["id"]
        assert competition["name"]


# --- the join ------------------------------------------------------------


def test_parses_every_match_in_the_capture(dense: str) -> None:
    matches = parse_schedule(dense)

    expected = sum(len(g.get("matches") or []) for g in competition_groups(dense))
    assert len(matches) == expected


def test_identity_comes_from_the_standard(dense: str) -> None:
    matches = parse_schedule(dense)

    assert all(m.identity_from_standard for m in matches), (
        "every match in this capture has a JSON-LD counterpart, so none should "
        "have fallen back to page state for its identity"
    )


def test_kickoffs_are_utc(dense: str) -> None:
    for match in parse_schedule(dense):
        assert match.kickoff_utc.endswith("Z")


# --- the collision that name-matching would hide -------------------------


def test_same_display_name_stays_two_competitions(dense: str) -> None:
    matches = parse_schedule(dense)

    named_premier_league = {
        m.competition_id for m in matches if m.competition_name == "Premier League"
    }
    assert named_premier_league == {EPL_ENGLAND, PL_KAZAKHSTAN}, (
        "two distinct competitions share this display name in one response; "
        "only the id separates them"
    )


def test_country_distinguishes_the_two(dense: str) -> None:
    by_id = {m.competition_id: m for m in parse_schedule(dense)}

    assert by_id[EPL_ENGLAND].competition_country == "England"
    assert by_id[PL_KAZAKHSTAN].competition_country == "Kazakhstan"


def test_english_and_kazakh_teams_do_not_mix(dense: str) -> None:
    english = {
        m.home_team for m in parse_schedule(dense) if m.competition_id == EPL_ENGLAND
    }
    kazakh = {
        m.home_team for m in parse_schedule(dense) if m.competition_id == PL_KAZAKHSTAN
    }

    assert english and kazakh
    assert not (english & kazakh)


# --- providers -----------------------------------------------------------


def test_providers_are_read_where_the_source_has_them(dense: str) -> None:
    english = [m for m in parse_schedule(dense) if m.competition_id == EPL_ENGLAND]

    assert english
    assert all(m.has_provider for m in english)
    assert any("Peacock" in m.providers for m in english)


def test_split_rights_yield_several_providers(dense: str) -> None:
    """One matchweek divides between broadcasters, which no league-level entry
    could express. This is why per-match data wins over the rights table."""
    english = [m for m in parse_schedule(dense) if m.competition_id == EPL_ENGLAND]

    assert any(len(m.providers) > 1 for m in english)
    distinct = {p for m in english for p in m.providers}
    assert len(distinct) > 1


def test_providers_are_names_only(dense: str) -> None:
    """Affiliate links and sponsorship flags are dropped; they describe the
    source's commercial arrangements, not who holds the rights."""
    for match in parse_schedule(dense):
        for provider in match.providers:
            assert isinstance(provider, str)
            assert "http" not in provider


def test_providers_are_deduplicated(dense: str) -> None:
    for match in parse_schedule(dense):
        assert len(match.providers) == len(set(match.providers))


def test_leagues_the_source_has_no_providers_for(dense: str) -> None:
    """The gap the rights table exists to fill. Recorded as a test so that a
    source that later starts answering for these is noticed rather than assumed."""
    matches = parse_schedule(dense)

    for competition_id in (MLS_NEXT_PRO, LIGA_MX):
        in_competition = [m for m in matches if m.competition_id == competition_id]
        assert in_competition, "capture should contain this competition"
        assert not any(m.has_provider for m in in_competition)


# --- a thin date ---------------------------------------------------------


def test_sparse_capture_parses(sparse: str) -> None:
    matches = parse_schedule(sparse)

    assert len(matches) == 1
    assert not matches[0].has_provider


# --- failure is not absence ----------------------------------------------


def test_missing_state_structure_raises(malformed: str) -> None:
    with pytest.raises(ScheduleParseError, match="liveScores"):
        parse_schedule(malformed)


def test_absent_script_raises() -> None:
    with pytest.raises(ScheduleParseError, match="changed shape"):
        parse_schedule("<html><body>nothing here</body></html>")


def test_unparseable_state_raises() -> None:
    html = (
        '<script id="__NEXT_DATA__" type="application/json">{not json}</script>'
    )
    with pytest.raises(ScheduleParseError, match="not valid JSON"):
        parse_schedule(html)


def test_a_readable_page_with_no_matches_is_not_an_error() -> None:
    """The other side of the same distinction: an empty schedule is a legitimate
    answer, and must not raise the exception that means the source broke."""
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        '{"props":{"pageProps":{"content":{"liveScores":[]}}}}</script>'
    )

    assert parse_schedule(html) == ()


def test_standard_survives_when_state_breaks(malformed: str) -> None:
    """Design D5 in one assertion: the durable half still parses after the
    private half has been renamed away."""
    assert len(sports_events(malformed)) == 1

    with pytest.raises(ScheduleParseError):
        competition_groups(malformed)
