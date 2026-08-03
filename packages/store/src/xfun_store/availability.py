"""Reading and writing where a match can be watched.

Kept out of `entities.py` on purpose. That module decomposes a `MatchSnapshot`
payload, and availability is deliberately not in a snapshot -- a model must not be
able to score a match differently according to who broadcasts it. Availability
travels beside the match, from acquisition to the API, without ever passing through
the scoring path.

`unknown` is a stored value rather than an absent row. Both read the same to a
caller, and `read_availability` answers `unknown` either way, but writing it
explicitly records that the question was asked and had no answer -- which is
different from never having looked.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

__all__ = [
    "MatchAvailability",
    "read_availability",
    "read_availability_map",
    "write_availability",
]

_UNKNOWN_STATUS = "unknown"
_KNOWN_STATUS = "known"


@dataclass(frozen=True)
class MatchAvailability:
    """Who carries a match, and how we came to believe it."""

    status: str = _UNKNOWN_STATUS
    providers: tuple[str, ...] = ()
    resolved_from: str | None = None

    @property
    def known(self) -> bool:
        return self.status == _KNOWN_STATUS

    def to_payload(self) -> dict[str, object]:
        """The `Availability` shape in `contracts/openapi.yaml`.

        `resolved_from` is deliberately not exposed. It is provenance for whoever
        maintains the data, not something a client should branch on -- a caller that
        treated a rights-table answer as less real than a source answer would be
        wrong, since the table is the more accurate of the two where it applies.
        """
        return {"status": self.status, "providers": list(self.providers)}


UNKNOWN = MatchAvailability()


def write_availability(
    conn: sqlite3.Connection,
    match_id: str,
    availability: MatchAvailability,
) -> None:
    """Record availability for one match, replacing any previous answer.

    Replacing rather than appending: unlike a score, this is not a historical
    record. A provider that changes has simply changed, and the previous answer is
    wrong rather than superseded.
    """
    if availability.known and not availability.providers:
        raise ValueError(
            f"{match_id}: availability is 'known' but names no provider. "
            "That would read as 'we checked and it is on nothing', which is a "
            "different and stronger claim than 'unknown'."
        )

    conn.execute(
        "INSERT OR REPLACE INTO match_availability "
        "(match_id, status, resolved_from, resolved_at) "
        "VALUES (?, ?, ?, datetime('now'))",
        (match_id, availability.status, availability.resolved_from),
    )
    conn.execute("DELETE FROM match_provider WHERE match_id = ?", (match_id,))
    conn.executemany(
        "INSERT INTO match_provider (match_id, position, name) VALUES (?, ?, ?)",
        [
            (match_id, position, name)
            for position, name in enumerate(availability.providers)
        ],
    )


def read_availability(conn: sqlite3.Connection, match_id: str) -> MatchAvailability:
    """Availability for one match. A match with no row answers `unknown`."""
    row = conn.execute(
        "SELECT status, resolved_from FROM match_availability WHERE match_id = ?",
        (match_id,),
    ).fetchone()
    if row is None:
        return UNKNOWN

    providers = tuple(
        r["name"]
        for r in conn.execute(
            "SELECT name FROM match_provider WHERE match_id = ? ORDER BY position",
            (match_id,),
        )
    )
    return MatchAvailability(
        status=row["status"],
        providers=providers,
        resolved_from=row["resolved_from"],
    )


def read_availability_map(
    conn: sqlite3.Connection,
    match_ids: Iterable[str] | None = None,
) -> Mapping[str, MatchAvailability]:
    """Availability for many matches at once.

    The API serves a list of matches, and asking per match would make rendering a
    page a function of how many matches are on. Matches with no row are absent from
    the result; callers are expected to treat absence as `unknown`, which is what
    `read_availability` does for the single case.
    """
    sql = "SELECT match_id, status, resolved_from FROM match_availability"
    params: list[str] = []
    wanted = list(match_ids) if match_ids is not None else None
    if wanted is not None:
        if not wanted:
            return {}
        sql += f" WHERE match_id IN ({','.join('?' * len(wanted))})"
        params = wanted

    rows = conn.execute(sql, params).fetchall()

    providers: dict[str, list[str]] = {}
    provider_sql = "SELECT match_id, name FROM match_provider"
    if wanted is not None:
        provider_sql += f" WHERE match_id IN ({','.join('?' * len(wanted))})"
    provider_sql += " ORDER BY match_id, position"
    for row in conn.execute(provider_sql, params):
        providers.setdefault(row["match_id"], []).append(row["name"])

    return {
        row["match_id"]: MatchAvailability(
            status=row["status"],
            providers=tuple(providers.get(row["match_id"], ())),
            resolved_from=row["resolved_from"],
        )
        for row in rows
    }
