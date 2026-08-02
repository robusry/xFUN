"""Joining entity-keyed collector output onto matches.

This is the machinery that lets a collector key its output by whatever entity its
source is organised around, and still have the result reach a model as a path on a
match. A collector reading team subreddits keys by team; a collector reading a
league table keys by league; neither has to know which match is which.

The set of joins is closed on purpose. Three kinds, three mechanical rules, no
judgement anywhere:

    match   ->  identity
    team    ->  the home and away sides of every match that team plays
    league  ->  every match in that league

Adding a fourth means defining a fourth join, which is a spec change rather than a
convenience. That closure is what stops collectors expressing match-level opinions
through the join -- attribution that needs judgement belongs to a model, not here.

The `{home, away}` shape a team join produces is not new: `form.home` and
`form.away` are already a team-keyed value joined onto a match.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from xfun_contract import EntityKind, Slate

__all__ = ["expand_paths", "join_values", "merge_signals", "signal_path"]


def signal_path(namespace: str, leaf: str, *, side: str | None = None) -> str:
    """The dotted path a model declares to read one collected leaf."""
    if side is None:
        return f"signals.{namespace}.{leaf}"
    return f"signals.{namespace}.{side}.{leaf}"


def expand_paths(namespace: str, provides: tuple[str, ...], kind: EntityKind) -> tuple[str, ...]:
    """Every full path a collector's declared leaves resolve to once joined.

    A team-keyed collector claims two paths per leaf, because the join produces a
    value per side. Registration checks uniqueness against these expanded paths
    rather than the bare leaves -- two team collectors in one namespace claiming the
    same leaf collide on both sides, and that must fail loudly.
    """
    if kind is EntityKind.TEAM:
        return tuple(
            signal_path(namespace, leaf, side=side)
            for leaf in provides
            for side in ("home", "away")
        )
    return tuple(signal_path(namespace, leaf) for leaf in provides)


def entity_ids(slate: Slate, kind: EntityKind) -> tuple[str, ...]:
    """The entities a collector of this kind is being asked about.

    The runtime derives coverage from this: whatever the collector does not return
    a value for, it was asked about and legitimately had nothing for.
    """
    if kind is EntityKind.MATCH:
        return slate.match_ids()
    if kind is EntityKind.TEAM:
        return tuple(t.id for t in slate.teams())
    return tuple(league.id for league in slate.leagues())


def join_values(
    slate: Slate,
    kind: EntityKind,
    values: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Map entity-keyed values onto matches.

    Returns `match_id -> namespace payload`. A match absent from the result got
    nothing from this collector, which is coverage rather than an error. A
    team-keyed value present for only one side yields only that side, so a model
    requiring the other side skips the match with a recorded reason.
    """
    joined: dict[str, dict[str, Any]] = {}

    for match in slate.matches:
        if kind is EntityKind.MATCH:
            payload = values.get(match.match_id)
            if payload:
                joined[match.match_id] = dict(payload)

        elif kind is EntityKind.LEAGUE:
            payload = values.get(match.league.id)
            if payload:
                joined[match.match_id] = dict(payload)

        else:  # EntityKind.TEAM
            sides: dict[str, Any] = {}
            for side, team in (("home", match.home_team), ("away", match.away_team)):
                payload = values.get(team.id)
                if payload:
                    sides[side] = dict(payload)
            if sides:
                joined[match.match_id] = sides

    return joined


def merge_signals(
    into: dict[str, dict[str, Any]],
    namespace: str,
    joined: Mapping[str, Mapping[str, Any]],
) -> None:
    """Fold one collector's joined output into the per-match signal tree.

    Mutates `into`, shaped `match_id -> {namespace -> payload}`. Several collectors
    may contribute to one namespace -- a namespace is a subject area, not a producer
    -- so payloads merge rather than replace. Leaf collisions cannot occur here
    because registration already rejected two producers claiming one path.
    """
    for match_id, payload in joined.items():
        namespaces = into.setdefault(match_id, {})
        existing = namespaces.setdefault(namespace, {})
        for key, value in payload.items():
            if isinstance(value, dict) and isinstance(existing.get(key), dict):
                existing[key].update(value)
            else:
                existing[key] = value
