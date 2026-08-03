"""Turning what the source said into this project's identifiers.

The source has perfectly good ids of its own -- opaque, stable, unique. They are not
used, per design D9. Adopting them would make replacing the source a migration of
every stored row rather than a change to one module, and D2 is explicit that this
source is the best option available today rather than a commitment.

So canonical ids are derived from names instead. That is also what makes re-running
acquisition converge: the same match produces the same id every time, so entity
writes upsert on a natural key with no stored correspondence to maintain.

`match-snapshot.json` and `slate.json` both constrain ids to `^[a-z0-9-]+$`, which is
why slugging is a requirement rather than a stylistic preference.

Two costs are accepted here and neither is defended as ideal. A team's slug comes
from its name alone, because the source attaches a country to competitions and not to
teams, so two clubs in different countries with the same name would collide -- River
Plate exists in Argentina and in Uruguay. And a team the source renames acquires a
new slug, and therefore a second canonical entity, silently. Both are recorded in D9.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from .parse import SourceMatch

__all__ = [
    "CanonicalIdError",
    "canonical_payload",
    "league_id",
    "match_id",
    "slugify",
    "team_id",
]

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_VALID_ID = re.compile(r"^[a-z0-9-]+$")


class CanonicalIdError(ValueError):
    """A name could not be reduced to a usable identifier.

    Raised rather than substituted. A placeholder id would flow into the store, the
    slate, and eventually a score, and every one of those would look fine.
    """


def slugify(text: str) -> str:
    """A lowercase, hyphenated identifier matching `^[a-z0-9-]+$`.

    Accents are folded rather than stripped, so `Atlético` becomes `atletico` and not
    `atltico`. Names that survive as digits alone are kept -- `Columbus Crew 2` is a
    distinct club from `Columbus Crew`, and dropping the numeral would merge them.
    """
    folded = unicodedata.normalize("NFKD", text)
    ascii_only = folded.encode("ascii", "ignore").decode("ascii")
    slug = _NON_ALPHANUMERIC.sub("-", ascii_only.lower()).strip("-")
    if not slug or not _VALID_ID.match(slug):
        raise CanonicalIdError(f"cannot derive an identifier from {text!r}")
    return slug


def league_id(name: str, country: str | None) -> str:
    """Country first, because the name alone is not unique.

    A single response carried both the English and the Kazakh `Premier League`.
    Without the country they would be one league holding both sets of teams, and
    nothing downstream would report a problem.
    """
    if country:
        return slugify(f"{country} {name}")
    return slugify(name)


def team_id(name: str) -> str:
    return slugify(name)


def match_id(league: str, kickoff_utc: str, home: str, away: str) -> str:
    """`<league>-<date>-<home>-<away>`, extending the fixtures' existing shape.

    The date rather than the full timestamp: a kickoff moved by an hour is the same
    match, and should not become a second one. A double-header between the same two
    clubs on one day in one competition would collide, which no competition in scope
    schedules.
    """
    date = kickoff_utc[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise CanonicalIdError(f"cannot read a date from kickoff {kickoff_utc!r}")
    return f"{league}-{date}-{home}-{away}"


def canonical_payload(match: SourceMatch) -> Mapping[str, Any]:
    """A `MatchSnapshot`-shaped payload carrying only what acquisition knows.

    Deliberately partial. `odds`, `form`, `table`, and `signals` are optional in the
    schema and are all absent here, because acquisition establishes which matches
    exist and where to watch them -- what a model reads about them belongs to another
    tier. Their absence is what makes every model skip every match, which is the
    expected outcome of this change rather than a gap to fill in later.

    Availability is absent too, and for a different reason: it is stored beside the
    match rather than in the snapshot, so that no model can score a match differently
    according to who broadcasts it. See design D6.
    """
    league = league_id(match.competition_name, match.competition_country)
    home = team_id(match.home_team)
    away = team_id(match.away_team)

    payload: dict[str, Any] = {
        "match_id": match_id(league, match.kickoff_utc, home, away),
        "league": {"id": league, "name": match.competition_name},
        "kickoff_utc": match.kickoff_utc,
        "home_team": {"id": home, "name": match.home_team},
        "away_team": {"id": away, "name": match.away_team},
    }
    if match.competition_country:
        # Omitted rather than null when unknown, matching how every other optional
        # field in the schema is handled: absent means absent.
        payload["league"]["country"] = match.competition_country
    return payload
