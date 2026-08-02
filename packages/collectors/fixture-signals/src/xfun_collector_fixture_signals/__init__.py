"""PLACEHOLDER COLLECTORS. Read files; talk to nothing.

Loads `contracts/fixtures/signals/<collector-id>.json` from disk. There is no HTTP
client here, no provider, and no credentials -- deliberately, so the skeleton runs
for a collaborator who has just cloned the repository with nothing configured. That
is the same bargain `FixtureFileAdapter` made for ingestion.

Three collectors rather than one, because there are three entity joins and a
walking skeleton that exercises two of them leaves the third only unit-tested:

    fixture-match   keys by match   -> joined by identity
    fixture-team    keys by team    -> joined onto home and away sides
    fixture-league  keys by league  -> broadcast to every match in the league

`fixture-team` deliberately returns one team, so that a match ends up with
`signals.reddit.home.*` and no `away` counterpart. A model requiring the away side
skips that match with a recorded reason, which is the routine case in this system.

**Replaced by:** the `add-live-ingestion` change, which selects a data provider and
writes real collectors against this interface. See docs/STUBS.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xfun_contract import CollectionResult, EntityKind, Slate
from xfun_runtime.paths import fixtures_dir

__all__ = [
    "FixtureLeagueSignals",
    "FixtureMatchSignals",
    "FixtureTeamSignals",
    "fixture_collectors",
]


class _FixtureSignals:
    """Shared plumbing: read one JSON file of entity_id -> values.

    Absence and failure are distinguished the way the contract requires. A missing
    entity in the file is absence -- a legitimate "nothing for this one". A missing
    FILE is failure: the source could not be consulted at all, so claiming every
    entity has nothing would assert something this collector cannot know.
    """

    refresh_after_seconds: int | None = None
    """Files do not go stale. A real collector declares a cadence its source
    deserves; see the note on enforcement in `xfun_contract.collection`."""

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory or (fixtures_dir() / "signals")

    @property
    def _path(self) -> Path:
        return self._directory / f"{self.collector_id}.json"

    def collect(self, slate: Slate) -> CollectionResult:
        try:
            values: dict[str, Any] = json.loads(self._path.read_text())
        except FileNotFoundError:
            return CollectionResult.unavailable(f"fixture file not found: {self._path.name}")
        except json.JSONDecodeError as exc:
            return CollectionResult.unavailable(f"fixture file is not valid JSON: {exc}")

        return CollectionResult(values=values)


class FixtureMatchSignals(_FixtureSignals):
    """Match-keyed signals, joined onto a match by identity."""

    collector_id = "fixture-match"
    namespace = "match-buzz"
    entity_kind = EntityKind.MATCH
    provides = ("mentions",)
    description = (
        "PLACEHOLDER. Invented per-match mention counts read from a fixture file. "
        "No provider, no network."
    )


class FixtureTeamSignals(_FixtureSignals):
    """Team-keyed signals, joined onto the home and away sides of a match.

    Returns one team on purpose, so the partial-coverage path is exercised.
    """

    collector_id = "fixture-team"
    namespace = "reddit"
    entity_kind = EntityKind.TEAM
    provides = ("excitement", "posts")
    description = (
        "PLACEHOLDER. Invented per-team interest levels read from a fixture file. "
        "Nothing here has been validated against whether anyone was actually excited."
    )


class FixtureLeagueSignals(_FixtureSignals):
    """League-keyed signals, broadcast to every match in the league."""

    collector_id = "fixture-league"
    namespace = "league-pulse"
    entity_kind = EntityKind.LEAGUE
    provides = ("table_volatility",)
    description = (
        "PLACEHOLDER. An invented per-league volatility index read from a fixture "
        "file. No provider, no network."
    )


def fixture_collectors(directory: Path | None = None) -> tuple[_FixtureSignals, ...]:
    """All three, in registration order."""
    return (
        FixtureMatchSignals(directory),
        FixtureTeamSignals(directory),
        FixtureLeagueSignals(directory),
    )
