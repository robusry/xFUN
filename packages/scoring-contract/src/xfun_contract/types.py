"""The two types that cross the scoring seam.

`MatchSnapshot` is everything a model is allowed to see. `ModelScore` is what the
platform stores. A model itself returns the smaller `ScoreResult` -- the runtime
attaches identity and provenance, so a model cannot get its own metadata wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .hashing import snapshot_hash

__all__ = ["MatchSnapshot", "ScoreResult", "ModelScore", "MISSING"]

MISSING = object()
"""Sentinel distinguishing 'feature absent' from 'feature present and null'."""


@dataclass(frozen=True)
class MatchSnapshot:
    """A single match as a model sees it.

    Wraps the raw payload rather than mirroring the schema in a class hierarchy.
    That keeps this type stable as the schema grows, and makes dotted-path feature
    declaration (`"odds.total_line"`) the natural way to ask for data.

    Conforms to contracts/schemas/match-snapshot.json.
    """

    data: Mapping[str, Any]

    @property
    def match_id(self) -> str:
        return self.data["match_id"]

    @property
    def league_id(self) -> str:
        return self.data["league"]["id"]

    @property
    def kickoff_utc(self) -> str:
        return self.data["kickoff_utc"]

    @property
    def hash(self) -> str:
        return snapshot_hash(self.data)

    def feature(self, path: str, default: Any = MISSING) -> Any:
        """Read a dotted path, e.g. `odds.total_line`.

        Returns `default` (MISSING by default) when any segment is absent. Optional
        blocks like `odds` are routinely missing -- that is coverage, not an error.
        """
        node: Any = self.data
        for segment in path.split("."):
            if not isinstance(node, Mapping) or segment not in node:
                return default
            node = node[segment]
        return node

    def has_features(self, paths: Iterable[str]) -> bool:
        return all(self.feature(p) is not MISSING for p in paths)

    def missing_features(self, paths: Iterable[str]) -> tuple[str, ...]:
        return tuple(p for p in paths if self.feature(p) is MISSING)


@dataclass(frozen=True)
class ScoreResult:
    """What a model returns.

    `raw_score` is on the model's own native scale -- a probability, a z-score, an
    arbitrary index. Models MUST NOT normalise: the platform percentile-ranks raw
    scores within a caller-chosen cohort. Two models' raw scores are not comparable.

    `components` is what makes a score arguable rather than merely asserted.
    """

    raw_score: float
    components: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelScore:
    """One model's score for one match, as stored.

    Append-only: never updated in place. Re-scoring inserts a new row with a new
    snapshot_hash, and the superseded row stays queryable.
    """

    match_id: str
    model_id: str
    model_version: str
    raw_score: float
    components: Mapping[str, float]
    snapshot_hash: str
    computed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Conforms to contracts/schemas/model-score.json."""
        out: dict[str, Any] = {
            "match_id": self.match_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "raw_score": self.raw_score,
            "components": dict(self.components),
            "snapshot_hash": self.snapshot_hash,
        }
        if self.computed_at is not None:
            out["computed_at"] = self.computed_at
        return out
