"""Goals scored in the last five completed matches, per team.

The first collector in this repository that reads a source rather than a file, and
the first thing a model consumes that is not invented.

It reads the same pages the schedule source reads -- goal.com's dated fixture pages
-- but backwards, from the day of the run. A single dated page answers for every team
in the world at once, which is why the fan-out here is over DATES rather than over the
slate's teams: one request per date serves four hundred teams, where one request per
team would serve one. The per-team pages this source also publishes were rejected for
a stronger reason than cost; see design D2 of `add-recent-goals-model`, and note that
they omit whole domestic leagues.

Three properties are worth reading the code for, because each is a wrong number
avoided rather than a feature:

- **Only finished matches count.** A postponed match on this source carries a 0-0
  score. Counting "any match with a score" would quietly treat a postponement as a
  goalless draw and a match kicking off as whatever it was at the moment of the fetch.

- **Fewer than five yields nothing.** Not four matches' worth of goals. A model cannot
  decline to score, so a partial sum would be ranked against complete ones and land
  near the bottom of the cohort for a reason that has nothing to do with the team.

- **A fetch failure discards the whole run.** Values gathered before the failure are
  thrown away rather than reported, because reporting them would say "these are the
  teams that have data", which is a claim this collector is no longer in a position to
  make. That is the absence-versus-failure distinction the contract requires.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import httpx
from xfun_contract import CollectionResult, EntityKind, Slate
from xfun_ingestion.schedule import (
    CanonicalIdError,
    ScheduleParseError,
    ScheduleSourceError,
    competition_groups,
    fetch_page,
    page_client,
    team_id,
)

__all__ = [
    "BOUND_DAYS",
    "MATCHES_COUNTED",
    "CapturedPages",
    "CompletedMatch",
    "LivePages",
    "PageSource",
    "RecentResults",
    "completed_matches",
]

MATCHES_COUNTED = 5
"""How many completed matches make up the value. Specified by the team, not derived.

A team with fewer than this carries no value at all -- see the module docstring."""

BOUND_DAYS = 120
"""No page older than this many days before the run is read.

Not configurable, for the same reason `WATCHABLE_WINDOW_DAYS` is not: the number is
load-bearing and a setting would invite tuning it per run until nobody could say what
a stored score had been computed from.

120 is measured rather than chosen for roundness. On 2026-08-04 -- a post-World-Cup
August, with most European leagues between seasons, and close to the worst case this
signal ever faces -- a 212-team slate reached 47% of teams at 45 days, 51% at 70, 77%
at 90, and 95% at 120. The flat stretch between 45 and 70 is the World Cup break; the
climb after it is the previous European season. Stopping at 90 would discard a fifth
of an August slate to save 48 MB. Mid-season the early stop in `collect` reaches every
team in roughly 35-45 dates and this bound never binds."""

_COMPLETED = "RESULT"
"""The one status this source uses for a finished match.

Matched positively rather than by excluding the states known to be bad. A status this
code has never seen therefore does not count, which leaves a team short of matches --
and a team short of matches produces no value. The other way round, an unrecognised
status would be counted, and a new source state would silently enter every total."""


@dataclass(frozen=True)
class CompletedMatch:
    """One finished match, as the source describes it.

    Team names are the SOURCE's. Matching them to teams on the slate happens in
    `collect`, and is deliberately done on the NAME rather than by assuming the slate's
    ids were derived from this source.
    """

    kickoff_utc: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int

    @property
    def identity(self) -> tuple[str, str, str]:
        """Enough to recognise this match if it turns up on two pages.

        Defensive: a match should appear only on its own date. If that ever stops
        being true, double-counting would inflate a total with no visible symptom.
        """
        return (self.kickoff_utc, self.home_team, self.away_team)


def completed_matches(html: str) -> tuple[CompletedMatch, ...]:
    """Every finished match on one dated page.

    Reads the page's embedded state, which is the only half that carries a score --
    the schema.org blocks that design D5 of `add-live-schedule` prefers for identity
    describe the fixture, not its result. So the durable half is unavailable here and
    this reads the fragile one, which breaks loudly rather than quietly when the source
    is redesigned: `competition_groups` raises rather than returning an empty list.

    A page with no finished matches is a legitimate answer -- most future dates, and
    plenty of past ones.
    """
    found: list[CompletedMatch] = []

    for group in competition_groups(html):
        for match in group.get("matches") or ():
            if not isinstance(match, dict) or match.get("status") != _COMPLETED:
                continue

            home = (match.get("teamA") or {}).get("name")
            away = (match.get("teamB") or {}).get("name")
            kickoff = match.get("startDate")
            score = match.get("score") or {}
            home_goals = score.get("teamA")
            away_goals = score.get("teamB")

            if not (home and away and kickoff):
                continue
            if not isinstance(home_goals, int) or not isinstance(away_goals, int):
                # Reported finished, but without a usable score. Skipping leaves the
                # team short rather than counting a match as goalless.
                continue

            found.append(
                CompletedMatch(
                    kickoff_utc=kickoff,
                    home_team=home,
                    away_team=away,
                    home_goals=home_goals,
                    away_goals=away_goals,
                )
            )

    return tuple(found)


class PageSource(Protocol):
    """Where dated pages come from.

    An injected seam, for the same reason `acquire_window` takes a `Fetcher`: a test
    that reached the live source would be slow, dependent on somebody else's uptime,
    and unable to exercise the failure paths at all. It is also what lets the default
    `./scripts/demo.sh` run this collector with no network.

    `dates` rather than "try each day and see" is deliberate. A source backed by a
    finite capture must be able to say it has run out, and running out of captures is
    not the same as a date having no matches -- one is the extent of a fixture, the
    other is a fact about football.
    """

    def dates(self, latest: date, bound_days: int) -> Iterator[date]:
        """The dates available to read, newest first, none older than the bound."""
        ...

    def page(self, day: date) -> str:
        """The page for one date, or `ScheduleSourceError` if it cannot be had."""
        ...


class LivePages:
    """Dated pages from the source, over the network.

    Opens one client for the whole scan, so a hundred-odd requests reuse a connection
    rather than opening a hundred.
    """

    def __init__(self) -> None:
        self._client: httpx.Client | None = None

    def dates(self, latest: date, bound_days: int) -> Iterator[date]:
        for offset in range(bound_days + 1):
            yield latest - timedelta(days=offset)

    def page(self, day: date) -> str:
        if self._client is None:
            self._client = page_client()
        return fetch_page(self._client, day)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


class CapturedPages:
    """Dated pages from golden fixtures on disk.

    The default path for `./scripts/demo.sh`, which must run on a fresh clone with no
    network. These are reduced captures of the source's own bytes -- see
    `scripts/capture_results_fixture.py` and `contracts/README.md` -- so the scan being
    exercised here is the real one, over real historical results.

    A date the capture does not hold is simply not yielded. It is not a gap in the data
    and not a failure; it is where the fixture stops.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def dates(self, latest: date, bound_days: int) -> Iterator[date]:
        earliest = latest - timedelta(days=bound_days)
        captured = sorted(
            (
                day
                for path in self._directory.glob("*.html")
                if (day := _date_of(path)) is not None
            ),
            reverse=True,
        )
        for day in captured:
            if earliest <= day <= latest:
                yield day

    def page(self, day: date) -> str:
        path = self._directory / f"{day.isoformat()}.html"
        try:
            return path.read_text()
        except OSError as exc:
            # `dates` only yields captures that exist, so arriving here means the
            # fixture set changed underneath the scan. That is a failure to read the
            # source, not a date with nothing on it.
            raise ScheduleSourceError(f"could not read capture {path.name}: {exc}") from None


def _date_of(path: Path) -> date | None:
    try:
        return date.fromisoformat(path.stem)
    except ValueError:
        return None


class RecentResults:
    """Goals scored in the last five completed matches, keyed by team."""

    collector_id = "recent-results"

    namespace = "form"
    """A subject area, never a producer. `signals.form.<side>.goals_scored_last_5` says
    nothing about goal.com, which is what lets the producer be replaced without every
    model that declares the path breaking."""

    entity_kind = EntityKind.TEAM
    provides = ("goals_scored_last_5",)

    description = (
        "Goals a team scored in its five most recent completed matches, in any "
        "competition, crossing seasons where five require it. Read from dated "
        "schedule pages. Teams with fewer than five completed matches inside a "
        "120-day bound carry no value."
    )

    refresh_after_seconds = 6 * 60 * 60
    """Six hours: results change when matches finish, and matches finish all day.

    Declared but not enforced -- nothing persists collected signals between runs yet,
    so every run scans afresh. Written down now because the cadence a source deserves
    is knowledge its author has and a reviewer should see, and because this collector
    is expensive enough that the day enforcement arrives it should already be right.
    See `add-collector-corpora`."""

    def __init__(
        self,
        pages: PageSource | None = None,
        *,
        as_of: date | None = None,
        bound_days: int = BOUND_DAYS,
    ) -> None:
        self._pages = pages or LivePages()
        self._as_of = as_of
        self._bound_days = bound_days

    def collect(self, slate: Slate) -> CollectionResult:
        """Scan backwards until every team has five completed matches, or the bound.

        The early stop is what makes this affordable in season: a mid-season slate is
        satisfied in roughly 35-45 dates, and only an off-season one walks the whole
        120. Nothing about the result depends on where it stopped -- a team either has
        five matches or it has no value.
        """
        wanted = _addressable(slate)
        if not wanted:
            return CollectionResult(values={})

        as_of = self._as_of or datetime.now(UTC).date()
        scored: dict[str, dict[tuple[str, str, str], tuple[str, int]]] = {
            team: {} for team in wanted.values()
        }

        for day in self._pages.dates(as_of, self._bound_days):
            try:
                html = self._pages.page(day)
                matches = completed_matches(html)
            except (ScheduleSourceError, ScheduleParseError) as exc:
                # Everything gathered so far is discarded. It is correct as far as it
                # goes -- the scan runs newest-first, so a team already holding five
                # holds the right five -- but reporting it would record every other
                # team as "asked, and had nothing", which is exactly the claim a
                # collector that just failed cannot make.
                return CollectionResult.unavailable(f"{day.isoformat()}: {exc}")

            for match in matches:
                for name, goals in (
                    (match.home_team, match.home_goals),
                    (match.away_team, match.away_goals),
                ):
                    try:
                        key = team_id(name)
                    except CanonicalIdError:
                        # A name this project cannot reduce to an identifier is a name
                        # the slate cannot hold either, so there is nothing to match.
                        continue
                    team = wanted.get(key)
                    if team is not None:
                        scored[team][match.identity] = (match.kickoff_utc, goals)

            if all(len(matches_for) >= MATCHES_COUNTED for matches_for in scored.values()):
                break

        return CollectionResult(values=_totals(scored))

    def close(self) -> None:
        closing = getattr(self._pages, "close", None)
        if closing is not None:
            closing()


def _addressable(slate: Slate) -> dict[str, str]:
    """Slate teams this collector can recognise on a page: match key -> team id.

    Matching is on the NAME, reduced by the same derivation acquisition uses, rather
    than on the slate's team id. The two coincide on the live path, where the slate was
    built from this source's own names -- but assuming they always coincide would tie
    this collector to how somebody else's ids happened to be minted. The golden fixture
    slate is the case in point: its teams are `ars` and `liv` with names `Arsenal` and
    `Liverpool`, and matching on the id would find nothing while matching on the name
    finds exactly the right club.

    Output is still keyed by the slate's id, because that is what the platform joins on.

    A name that two slate teams reduce to is dropped rather than resolved. Both River
    Plates are `river-plate`, and attributing one club's goals to another is precisely
    the kind of confidently wrong number this project would rather not produce; absence
    routes it to a recorded skip instead.
    """
    by_key: dict[str, str] = {}
    ambiguous: set[str] = set()

    for team in slate.teams():
        try:
            key = team_id(team.name)
        except CanonicalIdError:
            continue
        if key in by_key and by_key[key] != team.id:
            ambiguous.add(key)
        by_key[key] = team.id

    for key in ambiguous:
        del by_key[key]

    return by_key


def _totals(
    scored: Mapping[str, Mapping[tuple[str, str, str], tuple[str, int]]],
) -> dict[str, dict[str, Any]]:
    """Sum the five most recent per team, and omit teams that have fewer.

    Sorted by kickoff rather than trusting the scan order: the scan reads whole dates,
    and two matches on the same date arrive in the source's order, not in time order.
    A team can also finish holding six, because the last date read may have been the
    fifth AND sixth -- so the five to sum are chosen here rather than counted there.
    """
    totals: dict[str, dict[str, Any]] = {}

    for team, matches in scored.items():
        if len(matches) < MATCHES_COUNTED:
            continue
        recent = sorted(matches.values(), key=lambda entry: entry[0], reverse=True)
        totals[team] = {
            "goals_scored_last_5": sum(goals for _, goals in recent[:MATCHES_COUNTED])
        }

    return totals
