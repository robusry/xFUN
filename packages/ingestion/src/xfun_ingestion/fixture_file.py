"""PLACEHOLDER ADAPTER. Reads from disk; talks to nothing.

Loads the golden fixtures in `contracts/fixtures/snapshots/`. There is no HTTP
client here, no provider, and no credentials -- deliberately. The skeleton must
run for a collaborator who has just cloned the repository, with nothing
configured and no account anywhere.

Because it reads the same files the contract tests validate, it also proves the
snapshot schema round-trips: fixture -> canonical entities -> reassembled
snapshot, still schema-valid.

**Replaced by:** the `add-live-ingestion` change, which selects a data provider
and implements real fixture and odds adapters. See docs/STUBS.md.
"""

from __future__ import annotations

import json
from typing import Any, Iterator, Mapping

from xfun_runtime.paths import fixtures_dir

__all__ = ["FixtureFileAdapter"]


class FixtureFileAdapter:
    """Yields the golden fixture snapshots, in a stable order."""

    source_id = "fixture-file"
    description = (
        "PLACEHOLDER. Reads golden fixtures from contracts/fixtures/snapshots/. "
        "No network, no provider, no credentials."
    )

    def __init__(self, directory=None) -> None:
        self._directory = directory or (fixtures_dir() / "snapshots")

    def fetch(self) -> Iterator[Mapping[str, Any]]:
        for path in sorted(self._directory.glob("*.json")):
            yield json.loads(path.read_text())
