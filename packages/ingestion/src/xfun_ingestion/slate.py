"""Assembling the slate a collection run operates on.

The slate is the set of matches the run intends to score, decided before any
collector is invoked. It exists as a first-class thing rather than an implicit
iteration because collectors fan out from it: a team-keyed collector polls the
teams on the slate, a league-keyed one works from its leagues. Handing collectors
one match at a time would make a source that answers for twenty matches in one
request pay for twenty.

Two selection rules exist, and which one applies is recorded on the slate rather
than inferred.

`us-watchable` is the product rule: matches kicking off within ten days whose US
broadcaster is known. It became computable when availability stopped always
answering `unknown`.

`league-allowlist` is the older rule and stays reachable rather than being retired,
because the fixture path needs it. Fixture snapshots carry no availability, so
`us-watchable` would correctly admit none of them and a fresh clone would see an
empty slate.

Recording the rule matters more than it looks. A slate collected under one rule is
not interchangeable with a slate collected under another -- a social collector polls
different subreddits for different team sets, so its output is only meaningful next
to the slate that produced it. A run whose rule is unrecorded cannot be read back.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from xfun_contract import LeagueRef, MatchRef, Selection, Slate, TeamRef

__all__ = ["WATCHABLE_WINDOW_DAYS", "UnknownSelectionRule", "assemble_slate"]

WATCHABLE_WINDOW_DAYS = 10
"""How far ahead `us-watchable` looks, from the moment the run starts.

Not configurable, deliberately. The bound is what makes filtering on a known
provider defensible at all: beyond roughly two weeks a missing provider usually
means the broadcaster has not announced yet rather than that nobody carries the
match, so a larger window would silently drop matches for a reason that has nothing
to do with watchability. A setting would invite exactly that value.
"""

LEAGUE_ALLOWLIST = "league-allowlist"
US_WATCHABLE = "us-watchable"


class UnknownSelectionRule(ValueError):
    """A rule the slate schema does not admit. Both permitted values are recorded
    in `contracts/schemas/slate.json`, and a run made under an unrecorded rule
    would produce a slate nothing downstream could interpret."""


def _now_utc() -> datetime:
    return datetime.now(UTC)


def assemble_slate(
    conn: sqlite3.Connection,
    *,
    rule: str = LEAGUE_ALLOWLIST,
    leagues: tuple[str, ...] | None = None,
    window_start_utc: str | None = None,
    window_end_utc: str | None = None,
    now: datetime | None = None,
) -> Slate:
    """Build the slate from canonical match entities.

    Two rules, and which one applies is recorded on the slate rather than inferred.
    A slate collected under one is not interchangeable with a slate collected under
    another, so a run stays interpretable only if it says which it used.

    `us-watchable` admits a match when its kickoff falls within
    `WATCHABLE_WINDOW_DAYS` of the run AND at least one US provider is known for it.
    The window is measured from `now` rather than from a fixed date, because the
    product question is "what can I watch soon", which moves continuously.

    `league-allowlist` is the older rule and stays reachable. It is what the fixture
    path uses: fixture snapshots carry no availability at all, so `us-watchable`
    would correctly admit none of them, and the demo would show an empty slate on a
    clone with nothing configured.

    `leagues=None` under the allowlist admits every league present, which is what
    the fixture set wants and what a real deployment would never do.
    """
    if rule not in (LEAGUE_ALLOWLIST, US_WATCHABLE):
        raise UnknownSelectionRule(
            f"{rule!r} is not a selection rule. `contracts/schemas/slate.json` "
            f"admits {LEAGUE_ALLOWLIST!r} and {US_WATCHABLE!r}."
        )

    if rule == US_WATCHABLE:
        # Derived rather than accepted, so that a caller cannot ask for
        # `us-watchable` over an arbitrary range and get a slate whose recorded
        # rule no longer describes how it was built.
        start = now or _now_utc()
        window_start_utc = start.isoformat().replace("+00:00", "Z")
        window_end_utc = (
            (start + timedelta(days=WATCHABLE_WINDOW_DAYS))
            .isoformat()
            .replace("+00:00", "Z")
        )

    sql = (
        "SELECT m.match_id, m.kickoff_utc, "
        "       l.id AS league_id, l.name AS league_name, l.country AS league_country, "
        "       h.id AS home_id, h.name AS home_name, "
        "       a.id AS away_id, a.name AS away_name "
        "FROM match m "
        "JOIN league l ON l.id = m.league_id "
        "JOIN team h ON h.id = m.home_team_id "
        "JOIN team a ON a.id = m.away_team_id"
    )
    clauses: list[str] = []
    params: list[str] = []

    if rule == US_WATCHABLE:
        # An inner join, not a filter on a left join: a match with no availability
        # row and a match recorded as `unknown` are the same answer -- nobody knows
        # where to watch it -- and neither is watchable.
        sql += " JOIN match_availability av ON av.match_id = m.match_id"
        clauses.append("av.status = 'known'")

    if leagues:
        clauses.append(f"l.id IN ({','.join('?' * len(leagues))})")
        params.extend(leagues)
    if window_start_utc:
        clauses.append("m.kickoff_utc >= ?")
        params.append(window_start_utc)
    if window_end_utc:
        clauses.append("m.kickoff_utc < ?")
        params.append(window_end_utc)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY m.match_id"

    matches = tuple(
        MatchRef(
            match_id=row["match_id"],
            league=LeagueRef(
                id=row["league_id"],
                name=row["league_name"],
                country=row["league_country"],
            ),
            kickoff_utc=row["kickoff_utc"],
            home_team=TeamRef(id=row["home_id"], name=row["home_name"]),
            away_team=TeamRef(id=row["away_id"], name=row["away_name"]),
        )
        for row in conn.execute(sql, params).fetchall()
    )

    selection = Selection(
        rule=rule,
        # Under `us-watchable` the leagues are an OUTCOME rather than an input:
        # whichever leagues happened to have a watchable match. Recording them
        # anyway keeps a run readable months later, when which leagues were even
        # carried in the US has changed.
        leagues=tuple(leagues) if leagues else tuple(sorted({m.league.id for m in matches})),
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
    )

    return Slate(selection=selection, matches=matches)
