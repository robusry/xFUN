"""The seam between models and everything else.

This package is types and two hash functions. It has no dependencies and does no
I/O, because every model depends on it and anything added here is imposed on all
of them.

    from xfun_contract import MatchSnapshot, Model, ModelScore, ScoreResult

Collectors depend on it too, for the slate they fan out over and the result they
return. They are the one tier allowed to be impure -- see `collection`.
"""

from .collection import CollectionResult, Collector, EntityKind
from .hashing import canonical_json, slate_hash, snapshot_hash
from .model import Model
from .requirements import (
    FeaturePaths,
    Requirement,
    declared_feature_paths,
    declared_requirements,
)
from .slate import LeagueRef, MatchRef, Selection, Slate, TeamRef
from .types import MISSING, MatchSnapshot, ModelScore, ScoreResult

__all__ = [
    "MISSING",
    "CollectionResult",
    "Collector",
    "EntityKind",
    "FeaturePaths",
    "LeagueRef",
    "MatchRef",
    "MatchSnapshot",
    "Model",
    "ModelScore",
    "Requirement",
    "ScoreResult",
    "Selection",
    "Slate",
    "TeamRef",
    "canonical_json",
    "declared_feature_paths",
    "declared_requirements",
    "slate_hash",
    "snapshot_hash",
]
