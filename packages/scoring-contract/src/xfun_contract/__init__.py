"""The seam between models and everything else.

This package is types and one hash function. It has no dependencies and does no
I/O, because every model depends on it and anything added here is imposed on all
of them.

    from xfun_contract import MatchSnapshot, Model, ModelScore, ScoreResult
"""

from .hashing import canonical_json, snapshot_hash
from .model import Model
from .types import MISSING, MatchSnapshot, ModelScore, ScoreResult

__all__ = [
    "MISSING",
    "MatchSnapshot",
    "Model",
    "ModelScore",
    "ScoreResult",
    "canonical_json",
    "snapshot_hash",
]
