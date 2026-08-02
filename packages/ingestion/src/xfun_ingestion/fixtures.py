"""PLACEHOLDER SOURCE. Reads from disk; talks to nothing.

Loads the golden fixtures in `contracts/fixtures/snapshots/`. There is no HTTP
client here, no provider, and no credentials -- deliberately. The skeleton must run
for a collaborator who has just cloned the repository, with nothing configured and
no account anywhere.

Because it reads the same files the contract tests validate, it also proves the
snapshot schema round-trips: fixture -> canonical entities -> reassembled snapshot,
still schema-valid.

This yields the CANONICAL part of a match -- identity, kickoff, teams, league, and
the odds/form/table blocks. It does not yield signals: those are produced by
collectors keyed by whatever entity their source is organised around, and joined on
afterwards. The `signals` blocks present in these fixture files are the expected
RESULT of that join, not an input to it.

**Replaced by:** the `add-live-ingestion` change, which selects a data provider. See
docs/STUBS.md.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from xfun_runtime.paths import fixtures_dir

__all__ = ["fixture_payloads"]


def fixture_payloads(directory: Path | None = None) -> Iterator[Mapping[str, Any]]:
    """Yield the golden fixture snapshots, in a stable order.

    Idempotent in the sense ingestion requires: yields equivalent data every time,
    and writing the result twice leaves the store in the same state as writing it
    once, because entity writes are upserts on natural keys.
    """
    directory = directory or (fixtures_dir() / "snapshots")
    for path in sorted(directory.glob("*.json")):
        yield json.loads(path.read_text())
