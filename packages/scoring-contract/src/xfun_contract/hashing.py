"""Canonical hashing of match snapshots.

A stored score records the hash of the exact snapshot it was computed from. With
model_id and model_version, that is what makes any historical score reproducible:
given a row, you can find the input and re-run the model version that produced it.

The canonical form must never change casually. If it does, every previously stored
hash stops matching its input and reproducibility is silently lost. This function is
duplicated in the fixture generator for exactly that reason -- the two must agree.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["canonical_json", "slate_hash", "snapshot_hash"]


def canonical_json(data: Any) -> str:
    """Stable JSON: sorted keys, no incidental whitespace, unicode preserved.

    Accepts any JSON-serialisable value, not only a mapping -- a slate hashes a
    list of match refs.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def slate_hash(matches: Sequence[Mapping[str, Any]]) -> str:
    """Return `sha256:<hex>` for a slate's match set.

    Sorted by match_id before hashing, so a slate assembled in a different order is
    recognisably the same slate. The selection rule is deliberately NOT hashed: two
    runs that chose the same matches by different rules are looking at the same
    slate, and that must stay true when the rule changes from a league allowlist to
    broadcast availability.
    """
    ordered = sorted(matches, key=lambda m: m["match_id"])
    digest = hashlib.sha256(canonical_json(ordered).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def snapshot_hash(data: Mapping[str, Any]) -> str:
    """Return `sha256:<hex>` for a snapshot payload.

    Identical input always produces an identical hash, which is what lets the
    runtime skip re-scoring unchanged snapshots and lets an auditor confirm that a
    stored score came from the input it claims.
    """
    digest = hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
