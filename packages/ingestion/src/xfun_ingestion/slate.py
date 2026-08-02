"""Assembling the slate a collection run operates on.

The slate is the set of matches the run intends to score, decided before any
collector is invoked. It exists as a first-class thing rather than an implicit
iteration because collectors fan out from it: a team-keyed collector polls the
teams on the slate, a league-keyed one works from its leagues. Handing collectors
one match at a time would make a source that answers for twenty matches in one
request pay for twenty.

**The selection rule here is a placeholder.** The product scope is matches watchable
in the US, but broadcast availability always answers `unknown` today (see
docs/STUBS.md), so "watchable" is not yet computable. Until it is, the slate is a
league allowlist within a time window.

The rule is recorded on the slate rather than assumed, so that a run made under the
allowlist stays interpretable after the rule becomes broadcast-derived. That matters
more than it looks: a social collector polls different subreddits for different team
sets, so its output is only meaningful next to the slate that produced it.
"""

from __future__ import annotations

import sqlite3

from xfun_contract import LeagueRef, MatchRef, Selection, Slate, TeamRef

__all__ = ["assemble_slate"]


def assemble_slate(
    conn: sqlite3.Connection,
    *,
    leagues: tuple[str, ...] | None = None,
    window_start_utc: str | None = None,
    window_end_utc: str | None = None,
) -> Slate:
    """Build the slate from canonical match entities.

    PLACEHOLDER selection: every match in the allowlisted leagues whose kickoff
    falls in the window. `leagues=None` admits every league present, which is what
    the fixture set wants and what a real deployment would never do.

    Replaced by `add-broadcast-availability`, which makes `us-watchable` answerable.
    """
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
        rule="league-allowlist",
        leagues=tuple(leagues) if leagues else tuple(sorted({m.league.id for m in matches})),
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
    )

    return Slate(selection=selection, matches=matches)
