"""The source adapter interface.

Every data source -- a fixture list, an odds feed, a form provider -- implements
this. Runs must be idempotent: a scheduled job that fires twice produces the same
state as firing once, because it will fire twice eventually.

Adapters yield snapshot-shaped payloads. Assembling them into canonical entities
and back out into MatchSnapshots is the store's job, not the adapter's, so adding
a source never touches the scoring path.
"""

from __future__ import annotations

from typing import Any, Iterator, Mapping, Protocol, runtime_checkable

__all__ = ["SourceAdapter"]


@runtime_checkable
class SourceAdapter(Protocol):
    """A source of match data."""

    source_id: str
    """Stable identifier, for provenance and logging."""

    description: str

    def fetch(self) -> Iterator[Mapping[str, Any]]:
        """Yield payloads conforming to contracts/schemas/match-snapshot.json.

        MUST be idempotent: calling twice yields equivalent data, and writing the
        result twice leaves the store in the same state.
        """
        ...
