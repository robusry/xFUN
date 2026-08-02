"""The slate: the set of matches a collection run operates on.

A collection run starts by knowing every match it intends to score. Collectors
receive that set whole and choose their own fan-out -- an odds collector iterates
matches and queries each, a social collector reads `teams()` and polls per team, a
table collector works from `leagues()`. Handing a collector one match at a time
would force N requests where one would do, and push batching into every collector
as a private cache.

`MatchRef` is deliberately thin, and deliberately NOT a `MatchSnapshot`. A snapshot
is what a model sees after collection; a ref is what a collector needs in order to
go and fetch. Keeping them separate is what stops a collector from quietly growing
a dependency on data that collection is supposed to produce.

Conforms to contracts/schemas/slate.json.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .hashing import slate_hash

__all__ = ["LeagueRef", "MatchRef", "Selection", "Slate", "TeamRef"]


@dataclass(frozen=True)
class TeamRef:
    id: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name}


@dataclass(frozen=True)
class LeagueRef:
    id: str
    name: str
    country: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out = {"id": self.id, "name": self.name}
        # Omitted rather than null, matching how optional blocks are handled
        # everywhere else -- absent means absent.
        if self.country is not None:
            out["country"] = self.country
        return out


@dataclass(frozen=True)
class MatchRef:
    """Identity, timing, and the entities a collector fans out over. Nothing else.

    A collector that needs more than this is asking the wrong tier: the data it
    wants is either already a signal someone else collects, or a signal it should
    be collecting itself.
    """

    match_id: str
    league: LeagueRef
    kickoff_utc: str
    home_team: TeamRef
    away_team: TeamRef

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "league": self.league.to_dict(),
            "kickoff_utc": self.kickoff_utc,
            "home_team": self.home_team.to_dict(),
            "away_team": self.away_team.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MatchRef:
        league = data["league"]
        return cls(
            match_id=data["match_id"],
            league=LeagueRef(
                id=league["id"], name=league["name"], country=league.get("country")
            ),
            kickoff_utc=data["kickoff_utc"],
            home_team=TeamRef(**data["home_team"]),
            away_team=TeamRef(**data["away_team"]),
        )


@dataclass(frozen=True)
class Selection:
    """How the matches were chosen.

    Recorded alongside the slate because a slate collected under one rule is not
    interchangeable with a slate collected under another -- a social collector polls
    different subreddits for different team sets, so its output is only
    interpretable next to the slate that produced it.
    """

    rule: str
    leagues: tuple[str, ...] = ()
    window_start_utc: str | None = None
    window_end_utc: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"rule": self.rule}
        if self.leagues:
            out["leagues"] = list(self.leagues)
        if self.window_start_utc is not None:
            out["window_start_utc"] = self.window_start_utc
        if self.window_end_utc is not None:
            out["window_end_utc"] = self.window_end_utc
        return out


@dataclass(frozen=True)
class Slate:
    """Every match a collection run intends to score."""

    selection: Selection
    matches: tuple[MatchRef, ...]

    @property
    def slate_id(self) -> str:
        """Content hash over the match set.

        Identity is the matches alone, NOT the selection rule. Two runs that
        selected the same matches by different rules are looking at the same slate;
        how they got there is provenance, recorded in `selection`, not identity.
        """
        return slate_hash([m.to_dict() for m in self.matches])

    def match_ids(self) -> tuple[str, ...]:
        return tuple(m.match_id for m in self.matches)

    def teams(self) -> tuple[TeamRef, ...]:
        """Every team on the slate, deduplicated, in stable order.

        This is what a team-keyed collector fans out over.
        """
        seen: dict[str, TeamRef] = {}
        for match in self.matches:
            for team in (match.home_team, match.away_team):
                seen.setdefault(team.id, team)
        return tuple(seen[k] for k in sorted(seen))

    def leagues(self) -> tuple[LeagueRef, ...]:
        """Every league on the slate, deduplicated, in stable order."""
        seen: dict[str, LeagueRef] = {}
        for match in self.matches:
            seen.setdefault(match.league.id, match.league)
        return tuple(seen[k] for k in sorted(seen))

    def to_dict(self) -> dict[str, Any]:
        """Conforms to contracts/schemas/slate.json."""
        return {
            "slate_id": self.slate_id,
            "selection": self.selection.to_dict(),
            "matches": [m.to_dict() for m in sorted(self.matches, key=lambda m: m.match_id)],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Slate:
        selection = data["selection"]
        return cls(
            selection=Selection(
                rule=selection["rule"],
                leagues=tuple(selection.get("leagues", ())),
                window_start_utc=selection.get("window_start_utc"),
                window_end_utc=selection.get("window_end_utc"),
            ),
            matches=tuple(MatchRef.from_dict(m) for m in data["matches"]),
        )
