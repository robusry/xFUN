"""The collector interface.

Collectors are the inverse of models. A model is pure and may not touch the
network; a collector exists precisely to touch it. That inversion is the point --
it concentrates every impure, credentialed, rate-limited, occasionally-broken
interaction into one tier, so that scoring can stay reproducible.

Three constraints shape the interface:

- **The slate arrives whole.** A collector decides its own fan-out. Forcing one
  invocation per match would make a source that answers for twenty matches in one
  request pay for twenty.

- **Output is keyed by an entity, not always by a match.** A collector that reads
  team subreddits keys by team and lets the platform join onto matches. Requiring
  per-match output would force every collector to solve attribution, which is a
  judgement call rather than a mechanical one -- and one model may want strict
  match-thread matching where another wants loose team-mention sentiment. Baking
  either into the collector forecloses the other.

- **Absence and failure are different answers.** "This match has no thread" is
  permanent and correct. "The API returned 503" is transient and worth retrying.
  A collector that conflates them makes a week-long outage look like a source with
  nothing to say.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from .slate import Slate

__all__ = ["CollectionResult", "Collector", "EntityKind"]


class EntityKind(StrEnum):
    """What a collector keys its output by.

    A closed set, deliberately. Each member has exactly one mechanical join onto a
    match, and the joins are the whole reason collectors do not have to attribute
    their own output. Adding a member means defining a new join, which is a spec
    change rather than a convenience.
    """

    MATCH = "match"
    """Joined by identity."""

    TEAM = "team"
    """Joined onto the home and away sides of every match the team plays. Produces
    the same `{home, away}` shape that `form` already uses."""

    LEAGUE = "league"
    """Broadcast to every match in the league."""


@dataclass(frozen=True)
class CollectionResult:
    """What one collector returned for one slate.

    `values` maps entity id -> {leaf name -> value}. An entity simply absent from
    `values` is the collector saying "I looked and there is nothing", which is
    coverage rather than an error -- the runtime knows which entities it asked
    about and derives the absence count from the difference.

    `failure` set means the collector could NOT determine whether data exists. That
    is a different claim, and everything downstream treats it differently.
    """

    values: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    failure: str | None = None

    @property
    def failed(self) -> bool:
        return self.failure is not None

    @classmethod
    def unavailable(cls, reason: str) -> CollectionResult:
        """The source could not be reached or could not be trusted."""
        return cls(values={}, failure=reason)


@runtime_checkable
class Collector(Protocol):
    """A source of signals for a slate."""

    collector_id: str
    """Stable kebab-case identifier. Appears in the run record and never changes."""

    entity_kind: EntityKind
    """What `collect` keys its output by, and therefore how it joins onto matches."""

    provides: tuple[str, ...]
    """Leaf names this collector claims, WITHOUT the `signals.<namespace>.` prefix
    for namespaced signals -- the registry composes the full path. Exactly one
    registered producer may claim any given full path; a second claim is a
    registration error, not a last-writer-wins race."""

    namespace: str
    """The subject area these signals belong to, e.g. `reddit`. A namespace is NOT
    a producer id: several collectors may contribute to one namespace, and a
    signal may change producer without its path moving. That is what keeps a path
    stable for the models that declare it."""

    description: str
    """What this collector fetches and from where. Shown in the public registry."""

    refresh_after_seconds: int | None
    """How stale this collector's output may be before it is worth re-fetching.

    DECLARED BUT NOT YET ENFORCED. Nothing persists collected signals between runs
    in this change, so there is no staleness to measure -- every run collects
    afresh. The declaration exists now because cadence is a property of the source
    that its author knows and a reviewer should see, and because a chatty collector
    multiplies stored scores for every model downstream of it. Enforcement arrives
    with persistence in `add-collector-corpora`."""

    def collect(self, slate: Slate) -> CollectionResult:
        """Fetch signals for everything on the slate.

        Called once per run. Free to make one request or a hundred; that choice
        belongs to the collector, which knows its source.

        MUST be idempotent in the sense that ingestion already requires: running
        twice leaves the store in the same state as running once.

        MUST distinguish absence from failure. Returning an empty result when the
        source was unreachable asserts "nothing exists", which is a claim the
        collector is not in a position to make.
        """
        ...
