"""Canonical entities: writing them, and assembling snapshots back out of them.

This is the join between ingestion and scoring. Ingestion writes leagues, teams,
matches, odds, form, and table position. Snapshot assembly reads them back and
produces a schema-valid MatchSnapshot -- the only thing a model ever sees.

Optional blocks are omitted rather than emitted as nulls, so a match with no odds
produces a snapshot with no `odds` key, and models requiring odds skip it.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Mapping

from xfun_contract import MatchSnapshot

__all__ = ["write_snapshot_payload", "load_snapshots", "match_leagues"]


def write_snapshot_payload(conn: sqlite3.Connection, payload: Mapping[str, Any]) -> None:
    """Decompose one MatchSnapshot payload into canonical entity rows."""
    league = payload["league"]
    conn.execute(
        "INSERT OR REPLACE INTO league (id, name, country) VALUES (?, ?, ?)",
        (league["id"], league["name"], league.get("country")),
    )
    for side in ("home_team", "away_team"):
        team = payload[side]
        conn.execute(
            "INSERT OR REPLACE INTO team (id, name) VALUES (?, ?)",
            (team["id"], team["name"]),
        )

    conn.execute(
        "INSERT OR REPLACE INTO match "
        "(match_id, league_id, kickoff_utc, home_team_id, away_team_id) VALUES (?, ?, ?, ?, ?)",
        (
            payload["match_id"],
            league["id"],
            payload["kickoff_utc"],
            payload["home_team"]["id"],
            payload["away_team"]["id"],
        ),
    )

    odds = payload.get("odds")
    if odds:
        conn.execute(
            "INSERT OR REPLACE INTO odds_snapshot (match_id, captured_at, total_line, "
            "over_price, under_price, home_price, draw_price, away_price) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                payload["match_id"],
                odds.get("captured_at", payload["kickoff_utc"]),
                odds.get("total_line"),
                odds.get("over_price"),
                odds.get("under_price"),
                odds.get("home_price"),
                odds.get("draw_price"),
                odds.get("away_price"),
            ),
        )

    for side in ("home", "away"):
        form = (payload.get("form") or {}).get(side)
        if form:
            conn.execute(
                "INSERT OR REPLACE INTO team_form "
                "(match_id, side, matches, goals_for_avg, goals_against_avg) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    payload["match_id"],
                    side,
                    form["matches"],
                    form.get("goals_for_avg"),
                    form.get("goals_against_avg"),
                ),
            )

    table = payload.get("table")
    if table:
        conn.execute(
            "INSERT OR REPLACE INTO table_position "
            "(match_id, home_position, away_position, total_teams, matchweek) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                payload["match_id"],
                table.get("home_position"),
                table.get("away_position"),
                table.get("total_teams"),
                table.get("matchweek"),
            ),
        )
    conn.commit()


def _strip_nulls(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def load_snapshots(
    conn: sqlite3.Connection,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[MatchSnapshot, ...]:
    """Rebuild MatchSnapshots from canonical entities.

    The result must validate against contracts/schemas/match-snapshot.json; CI
    checks that on the fixture set.
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
    if date_from:
        clauses.append("m.kickoff_utc >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("m.kickoff_utc <= ?")
        params.append(date_to + "T23:59:59Z" if len(date_to) == 10 else date_to)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY m.kickoff_utc"

    snapshots: list[MatchSnapshot] = []

    for row in conn.execute(sql, params).fetchall():
        payload: dict[str, Any] = {
            "match_id": row["match_id"],
            "league": _strip_nulls(
                {
                    "id": row["league_id"],
                    "name": row["league_name"],
                    "country": row["league_country"],
                }
            ),
            "kickoff_utc": row["kickoff_utc"],
            "home_team": {"id": row["home_id"], "name": row["home_name"]},
            "away_team": {"id": row["away_id"], "name": row["away_name"]},
        }

        odds_row = conn.execute(
            "SELECT * FROM odds_snapshot WHERE match_id = ? "
            "ORDER BY captured_at DESC LIMIT 1",
            (row["match_id"],),
        ).fetchone()
        if odds_row:
            odds = _strip_nulls(
                {
                    "total_line": odds_row["total_line"],
                    "over_price": odds_row["over_price"],
                    "under_price": odds_row["under_price"],
                    "home_price": odds_row["home_price"],
                    "draw_price": odds_row["draw_price"],
                    "away_price": odds_row["away_price"],
                    "captured_at": odds_row["captured_at"],
                }
            )
            if odds:
                payload["odds"] = odds

        form: dict[str, Any] = {}
        for form_row in conn.execute(
            "SELECT * FROM team_form WHERE match_id = ?", (row["match_id"],)
        ):
            form[form_row["side"]] = _strip_nulls(
                {
                    "matches": form_row["matches"],
                    "goals_for_avg": form_row["goals_for_avg"],
                    "goals_against_avg": form_row["goals_against_avg"],
                }
            )
        if form:
            payload["form"] = form

        table_row = conn.execute(
            "SELECT * FROM table_position WHERE match_id = ?", (row["match_id"],)
        ).fetchone()
        if table_row:
            table = _strip_nulls(
                {
                    "home_position": table_row["home_position"],
                    "away_position": table_row["away_position"],
                    "total_teams": table_row["total_teams"],
                    "matchweek": table_row["matchweek"],
                }
            )
            if table:
                payload["table"] = table

        snapshots.append(MatchSnapshot(payload))

    return tuple(snapshots)


def match_leagues(conn: sqlite3.Connection) -> dict[str, str]:
    """match_id -> league_id. Needed by the league cohort resolver once built."""
    return {
        r["match_id"]: r["league_id"]
        for r in conn.execute("SELECT match_id, league_id FROM match")
    }


def iter_match_rows(conn: sqlite3.Connection) -> Iterable[sqlite3.Row]:
    return conn.execute("SELECT * FROM match ORDER BY kickoff_utc")
