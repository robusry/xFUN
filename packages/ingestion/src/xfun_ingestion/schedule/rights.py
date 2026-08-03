"""League-wide US broadcast rights, and resolving a match's providers.

Two steps, in this order, per design D3:

1. What the schedule source said about this match. It wins whenever it answers,
   because it is the only one of the two that can express a split -- a Premier League
   matchweek divides between NBC, USA Network, and Peacock, and no league-wide entry
   could say that.
2. The rights table, for leagues where every match really is on the same providers.
   Where the source is silent and the league is constant, a hand-verified line is
   MORE accurate than the source would have been: its provider data carries affiliate
   tracking, so it reflects who pays the source rather than who holds the rights.

Where neither answers, availability is `unknown`. That is a first-class answer here
and not a failure -- a confidently wrong provider is the error a viewer notices
immediately, and the whole reason the table is restricted to league-wide rights.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

__all__ = [
    "Availability",
    "LeagueRights",
    "RightsTable",
    "RightsTableError",
    "default_rights_path",
    "load_rights",
    "resolve_providers",
]


class RightsTableError(ValueError):
    """The rights table cannot be trusted as written, so it is not loaded at all.

    Refusing the whole file rather than skipping the bad entry is deliberate. A
    silently dropped league becomes matches that quietly stop reaching the slate,
    which looks identical to a quiet week.
    """


@dataclass(frozen=True)
class LeagueRights:
    league_id: str
    name: str
    providers: tuple[str, ...]
    verified_on: date
    source: str
    note: str | None = None


@dataclass(frozen=True)
class Availability:
    """Who carries a match, and whether we actually know.

    `unknown` with no providers is a real answer, not a null. See the Availability
    schema in `contracts/openapi.yaml`.
    """

    status: str
    providers: tuple[str, ...] = ()
    resolved_from: str | None = None
    """`source`, `rights-table`, or None. Provenance rather than decoration: an
    availability answer that came from a hand-maintained line ages differently from
    one the source produced, and only this says which."""

    @property
    def known(self) -> bool:
        return self.status == "known"


RightsTable = dict[str, LeagueRights]

_REQUIRED = ("providers", "verified_on", "source")


def default_rights_path() -> Path:
    """`packages/ingestion/rights/us-broadcast-rights.yaml`.

    Beside the package that reads it, mirroring how composition keeps `recipes/`
    beside `src/`. Both are values that move without a spec change.
    """
    return Path(__file__).resolve().parents[3] / "rights" / "us-broadcast-rights.yaml"


def load_rights(path: Path | None = None) -> RightsTable:
    """Read the table, refusing anything that cannot be trusted.

    `verified_on` and `source` are required, and their absence is an error rather
    than a default. US rights move between seasons, so an entry with no verification
    date is a provider of unknown vintage -- exactly the kind of quiet wrongness this
    file is most prone to.
    """
    path = path or default_rights_path()
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except FileNotFoundError:
        raise RightsTableError(f"no rights table at {path}") from None
    except yaml.YAMLError as exc:
        raise RightsTableError(f"rights table is not valid YAML: {exc}") from None

    leagues = raw.get("leagues") or {}
    if not isinstance(leagues, dict):
        raise RightsTableError("rights table must map `leagues` to league entries")

    table: RightsTable = {}
    for league_id, entry in leagues.items():
        if not isinstance(entry, dict):
            raise RightsTableError(f"{league_id}: entry must be a mapping")

        missing = [field for field in _REQUIRED if not entry.get(field)]
        if missing:
            raise RightsTableError(
                f"{league_id}: missing required field(s) {', '.join(missing)}. "
                "Every entry must record when it was verified and against what, "
                "because US rights move between seasons."
            )

        providers = entry["providers"]
        if not isinstance(providers, list) or not all(
            isinstance(p, str) and p for p in providers
        ):
            raise RightsTableError(f"{league_id}: providers must be a list of names")

        verified_on = entry["verified_on"]
        if not isinstance(verified_on, date):
            raise RightsTableError(
                f"{league_id}: verified_on must be a date (YYYY-MM-DD), "
                f"found {verified_on!r}"
            )

        table[league_id] = LeagueRights(
            league_id=league_id,
            name=entry.get("name") or league_id,
            providers=tuple(providers),
            verified_on=verified_on,
            source=entry["source"],
            note=entry.get("note"),
        )
    return table


def resolve_providers(
    source_providers: tuple[str, ...] | list[str],
    league_id: str,
    rights: RightsTable | None = None,
) -> Availability:
    """Providers for one match: the source first, the table second, else unknown."""
    if source_providers:
        return Availability(
            status="known",
            providers=tuple(source_providers),
            resolved_from="source",
        )

    entry = (rights or {}).get(league_id)
    if entry is not None:
        return Availability(
            status="known",
            providers=entry.providers,
            resolved_from="rights-table",
        )

    return Availability(status="unknown")
