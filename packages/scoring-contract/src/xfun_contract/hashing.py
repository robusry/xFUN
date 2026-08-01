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
from typing import Any, Mapping

__all__ = ["canonical_json", "snapshot_hash"]


def canonical_json(data: Mapping[str, Any]) -> str:
    """Stable JSON: sorted keys, no incidental whitespace, unicode preserved."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def snapshot_hash(data: Mapping[str, Any]) -> str:
    """Return `sha256:<hex>` for a snapshot payload.

    Identical input always produces an identical hash, which is what lets the
    runtime skip re-scoring unchanged snapshots and lets an auditor confirm that a
    stored score came from the input it claims.
    """
    digest = hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
