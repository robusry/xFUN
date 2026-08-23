"""The scan, and the four ways it could report a number that is quietly wrong.

Every test here runs without a network. The page source is an injected seam for
exactly that reason, and the last test in this file reads the golden captures the
offline demo uses, so the same code path is exercised on the source's own bytes.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from xfun_collector_recent_results import (
    BOUND_DAYS,
    CapturedPages,
    RecentResults,
    completed_matches,
)
from xfun_contract import LeagueRef, MatchRef, Selection, Slate, TeamRef
from xfun_ingestion.schedule import ScheduleSourceError

CAPTURES = (
    Path(__file__).resolve().parents[4] / "contracts" / "fixtures" / "schedule" / "results"
)
CAPTURE_AS_OF = date(2026, 8, 14)
"""The date the offline demo scans back from. Fixed, so the fixture path is
reproducible; `scripts/capture_results_fixture.py` was run with the same value."""


def match(
    home: str,
    away: str,
    home_goals: int | None,
    away_goals: int | None,
    *,
    kickoff: str,
    status: str = "RESULT",
) -> dict:
    score = None
    if home_goals is not None and away_goals is not None:
        score = {"teamA": home_goals, "teamB": away_goals}
    return {
        "startDate": kickoff,
        "status": status,
        "score": score,
        "teamA": {"name": home},
        "teamB": {"name": away},
    }


def page(*matches: dict, competition: str = "Premier League") -> str:
    """A page in the shape the source publishes: state, grouped by competition."""
    state = {
        "props": {
            "pageProps": {
                "content": {
                    "liveScores": [
                        {
                            "competition": {"id": "abc123", "name": competition},
                            "matches": list(matches),
                        }
                    ]
                }
            }
        }
    }
    return (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(state)
        + "</script></body></html>"
    )


class FakePages:
    """Pages from a dict of date -> html, recording what was asked for."""

    def __init__(self, pages: dict[date, str], *, fails_on: date | None = None) -> None:
        self._pages = pages
        self._fails_on = fails_on
        self.requested: list[date] = []

    def dates(self, latest: date, bound_days: int):
        earliest = latest - timedelta(days=bound_days)
        for day in sorted(self._pages, reverse=True):
            if earliest <= day <= latest:
                yield day

    def page(self, day: date) -> str:
        self.requested.append(day)
        if day == self._fails_on:
            raise ScheduleSourceError("the source refused the request (403)")
        return self._pages[day]


def slate_of(*teams: tuple[str, str]) -> Slate:
    """A slate of one match per pair of teams, given as (id, name)."""
    matches = []
    for index in range(0, len(teams), 2):
        (home_id, home_name), (away_id, away_name) = teams[index], teams[index + 1]
        matches.append(
            MatchRef(
                match_id=f"epl-2026-08-15-{home_id}-{away_id}",
                league=LeagueRef(id="epl", name="Premier League"),
                kickoff_utc="2026-08-15T19:00:00Z",
                home_team=TeamRef(id=home_id, name=home_name),
                away_team=TeamRef(id=away_id, name=away_name),
            )
        )
    return Slate(selection=Selection(rule="league-allowlist"), matches=tuple(matches))


def five_pages(team: str, goals: list[int], *, opponent: str = "Everton") -> dict[date, str]:
    """One completed match per date, walking backwards from 2026-08-10."""
    return {
        date(2026, 8, 10 - offset): page(
            match(
                team,
                opponent,
                scored,
                0,
                kickoff=f"2026-08-{10 - offset:02d}T19:00:00Z",
            )
        )
        for offset, scored in enumerate(goals)
    }


# --- what counts -------------------------------------------------------------


def test_only_finished_matches_count():
    """A postponed match on this source carries a 0-0 score, and a live one carries a
    running score. Counting "has a score" would treat a postponement as a goalless
    draw -- a number that looks entirely plausible and is wrong."""
    html = page(
        match("Arsenal", "Everton", 3, 1, kickoff="2026-08-10T19:00:00Z"),
        match("Arsenal", "Burnley", 0, 0, kickoff="2026-08-09T19:00:00Z", status="POSTPONED"),
        match("Arsenal", "Brentford", 1, 0, kickoff="2026-08-08T19:00:00Z", status="LIVE"),
        match("Arsenal", "Chelsea", 0, 0, kickoff="2026-08-07T19:00:00Z", status="CANCELLED"),
        match("Arsenal", "Liverpool", None, None, kickoff="2026-08-20T19:00:00Z", status="FIXTURE"),
    )
    assert [m.home_goals for m in completed_matches(html)] == [3]


def test_an_unrecognised_status_does_not_count():
    """Matched positively, so a state nobody here has seen leaves a team short rather
    than entering a total."""
    html = page(match("Arsenal", "Everton", 4, 0, kickoff="2026-08-10T19:00:00Z", status="AET"))
    assert completed_matches(html) == ()


def test_a_finished_match_without_a_usable_score_does_not_count():
    html = page(match("Arsenal", "Everton", None, None, kickoff="2026-08-10T19:00:00Z"))
    assert completed_matches(html) == ()


def test_goals_scored_by_each_side_are_read_from_the_right_side():
    html = page(match("Arsenal", "Everton", 3, 1, kickoff="2026-08-10T19:00:00Z"))
    (played,) = completed_matches(html)
    assert (played.home_team, played.home_goals) == ("Arsenal", 3)
    assert (played.away_team, played.away_goals) == ("Everton", 1)


# --- the value ---------------------------------------------------------------


def test_five_most_recent_are_summed():
    pages = five_pages("Arsenal", [2, 0, 1, 3, 1])
    collector = RecentResults(FakePages(pages), as_of=date(2026, 8, 10))
    result = collector.collect(slate_of(("ars", "Arsenal"), ("eve", "Everton")))
    assert result.values["ars"] == {"goals_scored_last_5": 7}


def test_a_sixth_older_match_does_not_count():
    pages = five_pages("Arsenal", [2, 0, 1, 3, 1, 9])
    collector = RecentResults(FakePages(pages), as_of=date(2026, 8, 10))
    result = collector.collect(slate_of(("ars", "Arsenal"), ("eve", "Everton")))
    assert result.values["ars"] == {"goals_scored_last_5": 7}


def test_matches_are_ranked_by_kickoff_not_by_the_order_they_were_read():
    """Two matches on one page arrive in the source's order. If the five were taken in
    encounter order, the sixth-most-recent could displace the fifth."""
    pages = {
        date(2026, 8, 10): page(
            match("Arsenal", "Everton", 1, 0, kickoff="2026-08-10T12:00:00Z"),
            match("Arsenal", "Burnley", 5, 0, kickoff="2026-08-10T19:00:00Z"),
        ),
        date(2026, 8, 9): page(
            match("Arsenal", "Chelsea", 2, 0, kickoff="2026-08-09T19:00:00Z"),
            match("Arsenal", "Brentford", 3, 0, kickoff="2026-08-09T12:00:00Z"),
            match("Arsenal", "Liverpool", 4, 0, kickoff="2026-08-09T09:00:00Z"),
            match("Arsenal", "Newcastle", 100, 0, kickoff="2026-08-01T19:00:00Z"),
        ),
    }
    collector = RecentResults(FakePages(pages), as_of=date(2026, 8, 10))
    result = collector.collect(slate_of(("ars", "Arsenal"), ("eve", "Everton")))
    assert result.values["ars"] == {"goals_scored_last_5": 1 + 5 + 2 + 3 + 4}


def test_a_match_repeated_across_pages_is_counted_once():
    """Defensive: a match should appear only on its own date. Double counting would
    inflate a total with no visible symptom."""
    repeated = match("Arsenal", "Everton", 3, 0, kickoff="2026-08-10T19:00:00Z")
    pages = five_pages("Arsenal", [2, 0, 1, 3, 1])
    pages[date(2026, 8, 4)] = page(repeated)
    pages[date(2026, 8, 10)] = page(repeated)

    collector = RecentResults(FakePages(pages), as_of=date(2026, 8, 10))
    result = collector.collect(slate_of(("ars", "Arsenal"), ("eve", "Everton")))
    assert result.values["ars"] == {"goals_scored_last_5": 3 + 0 + 1 + 3 + 1}


def test_goals_conceded_are_not_counted():
    pages = {
        date(2026, 8, 10 - offset): page(
            match("Everton", "Arsenal", 4, 1, kickoff=f"2026-08-{10 - offset:02d}T19:00:00Z")
        )
        for offset in range(5)
    }
    collector = RecentResults(FakePages(pages), as_of=date(2026, 8, 10))
    result = collector.collect(slate_of(("ars", "Arsenal"), ("eve", "Everton")))
    assert result.values["ars"] == {"goals_scored_last_5": 5}
    assert result.values["eve"] == {"goals_scored_last_5": 20}


# --- coverage ----------------------------------------------------------------


def test_fewer_than_five_yields_no_value_at_all():
    """Not a partial sum. A model cannot decline to score, so a sum over three would be
    ranked against sums over five for a reason unrelated to the team."""
    collector = RecentResults(
        FakePages(five_pages("Arsenal", [2, 0, 1])), as_of=date(2026, 8, 10)
    )
    result = collector.collect(slate_of(("ars", "Arsenal"), ("eve", "Everton")))
    assert not result.failed
    assert "ars" not in result.values


def test_one_side_short_leaves_the_other_present():
    pages = five_pages("Arsenal", [2, 0, 1, 3, 1], opponent="Everton")
    pages[date(2026, 8, 3)] = page(
        match("Liverpool", "Burnley", 2, 0, kickoff="2026-08-03T19:00:00Z")
    )
    collector = RecentResults(FakePages(pages), as_of=date(2026, 8, 10))
    result = collector.collect(slate_of(("ars", "Arsenal"), ("liv", "Liverpool")))
    assert "ars" in result.values
    assert "liv" not in result.values


def test_teams_are_matched_by_name_not_by_the_slates_id():
    """The golden fixture slate calls Arsenal `ars`. Matching on the id would find
    nothing; matching on the name derivation finds the right club, and the value is
    still keyed by the slate's id because that is what the platform joins on."""
    collector = RecentResults(
        FakePages(five_pages("Arsenal", [1, 1, 1, 1, 1])), as_of=date(2026, 8, 10)
    )
    result = collector.collect(slate_of(("ars", "Arsenal"), ("eve", "Everton")))
    assert set(result.values) >= {"ars"}


def test_two_slate_teams_with_one_name_are_both_dropped():
    """Both River Plates reduce to `river-plate`. Attributing one club's goals to the
    other is worse than admitting the gap."""
    pages = {
        date(2026, 8, 10 - offset): page(
            match("River Plate", "Everton", 2, 0, kickoff=f"2026-08-{10 - offset:02d}T19:00:00Z")
        )
        for offset in range(5)
    }
    collector = RecentResults(FakePages(pages), as_of=date(2026, 8, 10))
    result = collector.collect(
        slate_of(
            ("river-arg", "River Plate"),
            ("eve", "Everton"),
            ("river-uru", "River Plate"),
            ("bur", "Burnley"),
        )
    )
    assert "river-arg" not in result.values
    assert "river-uru" not in result.values


# --- stopping ----------------------------------------------------------------


def test_the_scan_stops_once_every_team_has_five():
    pages = five_pages("Arsenal", [1, 1, 1, 1, 1])
    pages.update(
        {
            date(2026, 7, 20): page(
                match("Arsenal", "Everton", 9, 0, kickoff="2026-07-20T19:00:00Z")
            )
        }
    )
    source = FakePages(pages)
    RecentResults(source, as_of=date(2026, 8, 10)).collect(
        slate_of(("ars", "Arsenal"), ("eve", "Everton"))
    )
    assert date(2026, 7, 20) not in source.requested


def test_a_page_older_than_the_bound_is_not_read():
    pages = five_pages("Arsenal", [1, 1, 1])
    pages[date(2025, 1, 1)] = page(
        match("Arsenal", "Everton", 4, 0, kickoff="2025-01-01T19:00:00Z")
    )
    source = FakePages(pages)
    result = RecentResults(source, as_of=date(2026, 8, 10), bound_days=30).collect(
        slate_of(("ars", "Arsenal"), ("eve", "Everton"))
    )
    assert date(2025, 1, 1) not in source.requested
    assert "ars" not in result.values


def test_the_bound_is_a_stated_number():
    assert BOUND_DAYS == 120


# --- failure is not absence --------------------------------------------------


def test_a_fetch_failure_discards_the_whole_run():
    """The values gathered before the failure are correct as far as they go. Reporting
    them would record every other team as 'asked, and had nothing' -- a claim a
    collector that just failed is not in a position to make."""
    pages = five_pages("Arsenal", [1, 1, 1, 1, 1])
    pages[date(2026, 8, 4)] = page()
    source = FakePages(pages, fails_on=date(2026, 8, 8))

    result = RecentResults(source, as_of=date(2026, 8, 10)).collect(
        slate_of(("ars", "Arsenal"), ("eve", "Everton"))
    )
    assert result.failed
    assert "403" in result.failure
    assert result.values == {}


def test_a_page_that_changed_shape_is_a_failure_not_an_empty_week():
    source = FakePages({date(2026, 8, 10): "<html><body>redesigned</body></html>"})
    result = RecentResults(source, as_of=date(2026, 8, 10)).collect(
        slate_of(("ars", "Arsenal"), ("eve", "Everton"))
    )
    assert result.failed
    assert "changed shape" in result.failure


def test_an_empty_slate_asks_the_source_nothing():
    source = FakePages(five_pages("Arsenal", [1, 1, 1, 1, 1]))
    result = RecentResults(source, as_of=date(2026, 8, 10)).collect(
        Slate(selection=Selection(rule="league-allowlist"), matches=())
    )
    assert not result.failed
    assert source.requested == []


# --- the golden captures -----------------------------------------------------


NAMED_DIFFERENTLY_BY_THE_SOURCE = {"int"}
"""Fixture teams the source does not call by the fixture's name.

The golden snapshot calls Inter `Internazionale`; goal.com calls them `Inter`, so the
two reduce to different keys and the scan finds nothing. Left as it is on purpose. The
snapshots are authored contract examples, and editing one to match a third party's
vocabulary would make this project's fixtures answerable to somebody else's naming --
while the failure it produces is absence, which is exactly what should happen when a
club cannot be recognised. The Serie A fixture match comes back unscored with a reason,
on the demo path, from real data. That is the partial-coverage path demonstrating
itself."""


def fixture_teams() -> set[tuple[str, str]]:
    fixtures = CAPTURES.parent.parent / "snapshots"
    return {
        (payload[side]["id"], payload[side]["name"])
        for path in sorted(fixtures.glob("*.json"))
        for payload in [json.loads(path.read_text())]
        for side in ("home_team", "away_team")
    }


@pytest.mark.skipif(not CAPTURES.exists(), reason="captures not present")
def test_the_offline_captures_cover_the_fixture_teams():
    """The offline demo's data, read through the real scan. If this fails, the demo
    would show unscored matches on a clone with no network."""
    teams = fixture_teams()
    result = RecentResults(CapturedPages(CAPTURES), as_of=CAPTURE_AS_OF).collect(
        slate_of(*sorted(teams))
    )

    assert not result.failed
    expected = {team_id for team_id, _ in teams} - NAMED_DIFFERENTLY_BY_THE_SOURCE
    missing = sorted(expected - set(result.values))
    assert not missing, f"no captured value for {missing}"
    assert all(
        isinstance(value["goals_scored_last_5"], int) for value in result.values.values()
    )


@pytest.mark.skipif(not CAPTURES.exists(), reason="captures not present")
def test_a_team_the_source_names_differently_is_absent_rather_than_wrong():
    """Guards the reasoning above: this must stay a gap rather than become a value
    attributed by a looser match. A fuzzy name match would eventually put one club's
    goals on another, and nothing downstream would show a symptom."""
    result = RecentResults(CapturedPages(CAPTURES), as_of=CAPTURE_AS_OF).collect(
        slate_of(*sorted(fixture_teams()))
    )
    assert not (NAMED_DIFFERENTLY_BY_THE_SOURCE & set(result.values))
