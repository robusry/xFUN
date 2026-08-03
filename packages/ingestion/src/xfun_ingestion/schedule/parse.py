"""Reading a schedule page into matches.

The source publishes the same fixtures twice, in two formats with different
durability, and this module deliberately reads both rather than picking the more
convenient one.

**schema.org `SportsEvent`, as JSON-LD.** A published standard the source does not
own. Carries identity, kickoff, venue, and status. Does NOT carry the competition or
the broadcasters.

**The page's own embedded state.** A private implementation detail of somebody
else's front end. Carries the competition -- with a stable id and a country -- and
the TV providers.

Identity and timing are taken from the standard, competition and providers from the
state, per design D5. The two agree today, so at runtime the preference rarely
changes a value; what it changes is what breaks when the source is redesigned, and
which half a future reader should trust when they disagree.

The competition id is not a nicety. The source's display names collide across
countries -- `Premier League` alone spans England, Kazakhstan, Azerbaijan, Belarus,
Bosnia, and Canada, and on a single sampled date the England and Kazakhstan
competitions appeared in the same response. Matching on name would silently merge
them. Only `competition.id` separates them, so it is what this module keys on and
what the golden fixture is built to exercise.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "ScheduleParseError",
    "SourceMatch",
    "competition_groups",
    "parse_schedule",
    "sports_events",
]

_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)
_LD_JSON = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL
)


class ScheduleParseError(Exception):
    """The response was fetched but does not have the shape this parser reads.

    Distinct from "the window held no matches", and the distinction is the point.
    Both leave the slate empty, and only this exception separates a source that
    changed shape from a quiet weekend. See the failure requirement in
    `schedule-acquisition`.
    """


@dataclass(frozen=True)
class SourceMatch:
    """One fixture as the source describes it, before any canonical mapping.

    Team and competition identifiers here are the SOURCE's, not this project's.
    Nothing downstream should treat them as canonical -- that translation is a
    separate step, deliberately, because the source's ids are stable only within
    the source.
    """

    home_team: str
    away_team: str
    kickoff_utc: str
    competition_id: str
    competition_name: str
    competition_country: str | None = None
    providers: tuple[str, ...] = ()
    venue: str | None = None
    identity_from_standard: bool = True
    """False when no JSON-LD block matched and identity fell back to page state.

    Recorded rather than hidden: a response where this is false for most matches is
    one where the durable half of D5 has stopped working, which is worth noticing
    before the fragile half fails too."""

    @property
    def has_provider(self) -> bool:
        return bool(self.providers)


def sports_events(html: str) -> list[Mapping[str, Any]]:
    """Every schema.org `SportsEvent` block, in document order.

    A page carrying no such block is not an error here. Absence of matches is a
    legitimate answer for a quiet date, and only the page state can distinguish
    that from a source that changed shape.
    """
    events: list[Mapping[str, Any]] = []
    for block in _LD_JSON.findall(html):
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            # One malformed block among many is not a structural failure. The
            # state parser decides whether the response as a whole is readable.
            continue
        if isinstance(parsed, dict) and parsed.get("@type") == "SportsEvent":
            events.append(parsed)
    return events


def competition_groups(html: str) -> list[Mapping[str, Any]]:
    """Matches grouped by competition, from the page's embedded state.

    Raises rather than returning empty when the structure is missing, because an
    empty list would be indistinguishable from a date with nothing on it.
    """
    found = _NEXT_DATA.search(html)
    if found is None:
        raise ScheduleParseError(
            "no __NEXT_DATA__ script in response; the source changed shape"
        )
    try:
        state = json.loads(found.group(1))
    except json.JSONDecodeError as exc:
        raise ScheduleParseError(f"__NEXT_DATA__ is not valid JSON: {exc}") from None

    try:
        groups = state["props"]["pageProps"]["content"]["liveScores"]
    except (KeyError, TypeError) as exc:
        raise ScheduleParseError(
            f"page state no longer holds props.pageProps.content.liveScores ({exc}); "
            "the source changed shape"
        ) from None

    if not isinstance(groups, list):
        raise ScheduleParseError(
            f"expected liveScores to be a list, found {type(groups).__name__}"
        )
    return groups


def _identity_key(home: str | None, away: str | None, kickoff: str | None) -> tuple:
    return (home, away, kickoff)


def _index_events(events: list[Mapping[str, Any]]) -> dict[tuple, Mapping[str, Any]]:
    index: dict[tuple, Mapping[str, Any]] = {}
    for event in events:
        key = _identity_key(
            (event.get("homeTeam") or {}).get("name"),
            (event.get("awayTeam") or {}).get("name"),
            event.get("startDate"),
        )
        index.setdefault(key, event)
    return index


def _providers(match: Mapping[str, Any]) -> tuple[str, ...]:
    """Provider names, deduplicated, in the order the source lists them.

    Everything else on a channel entry -- logos, affiliate links, sponsorship flags
    -- is dropped here. Those exist to monetise the source's own page and say
    nothing about who holds the rights.
    """
    seen: list[str] = []
    for channel in match.get("tvChannels") or ():
        name = (channel or {}).get("name")
        if name and name not in seen:
            seen.append(name)
    return tuple(seen)


def _matches_in(group: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    for match in group.get("matches") or ():
        if isinstance(match, dict):
            yield match


def parse_schedule(html: str) -> tuple[SourceMatch, ...]:
    """Every match on a schedule page, keyed by the source's own identifiers.

    Iterates the page state, because that is the only half that knows which
    competition a match belongs to, and enriches each match from the JSON-LD index.
    Where a match has no JSON-LD counterpart it is still returned, with
    `identity_from_standard` false, since dropping a real fixture to preserve a
    stylistic preference about formats would be the wrong trade.
    """
    groups = competition_groups(html)
    index = _index_events(sports_events(html))

    parsed: list[SourceMatch] = []
    for group in groups:
        competition = group.get("competition") or {}
        competition_id = competition.get("id")
        if not competition_id:
            # A group with no competition id cannot be attributed to a league, and
            # a name is not a substitute -- see the module docstring on collisions.
            continue

        for match in _matches_in(group):
            team_a = (match.get("teamA") or {}).get("name")
            team_b = (match.get("teamB") or {}).get("name")
            kickoff = match.get("startDate")
            if not (team_a and team_b and kickoff):
                continue

            event = index.get(_identity_key(team_a, team_b, kickoff))
            if event is not None:
                home = (event.get("homeTeam") or {}).get("name") or team_a
                away = (event.get("awayTeam") or {}).get("name") or team_b
                start = event.get("startDate") or kickoff
                venue = (event.get("location") or {}).get("name")
            else:
                home, away, start = team_a, team_b, kickoff
                venue = (match.get("venue") or {}).get("name")

            parsed.append(
                SourceMatch(
                    home_team=home,
                    away_team=away,
                    kickoff_utc=start,
                    competition_id=competition_id,
                    competition_name=competition.get("name") or "",
                    competition_country=(competition.get("area") or {}).get("name"),
                    providers=_providers(match),
                    venue=venue,
                    identity_from_standard=event is not None,
                )
            )
    return tuple(parsed)
