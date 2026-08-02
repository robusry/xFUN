"""Combining calibrated model scores into one number.

Composition operates on CALIBRATED scores, never raw ones -- raw scores live on
incomparable native scales, and averaging them would produce plausible nonsense.

It is also pure arithmetic over scores that already exist. Recomposing the entire
historical set re-runs no models and takes seconds, which is the property that
makes "we changed our minds about the blend again" cheap.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from xfun_runtime.calibration import CalibratedScore

from .recipe import IMPLEMENTED_POLICIES, PolicyNotImplemented, Recipe

__all__ = ["ComposedScore", "Contributor", "compose_all", "compose_match"]


@dataclass(frozen=True)
class Contributor:
    model_id: str
    weight: float
    calibrated_score: float

    def to_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "weight": round(self.weight, 4),
            "calibrated_score": self.calibrated_score,
        }


@dataclass(frozen=True)
class ComposedScore:
    """`value` is None when no composed score could be produced; `reason` says why.

    A null with a reason is a better answer than a number that pretends the missing
    models did not matter.
    """

    value: float | None
    reason: str | None = None
    contributors: tuple[Contributor, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "reason": self.reason,
            "contributors": [c.to_dict() for c in self.contributors],
        }


def compose_match(scores: Sequence[CalibratedScore], recipe: Recipe) -> ComposedScore:
    """Compose one match's calibrated scores under a recipe."""
    if recipe.on_missing not in IMPLEMENTED_POLICIES:
        raise PolicyNotImplemented(recipe.on_missing)

    available = {s.model_id: s for s in scores if s.model_id in recipe.models}
    missing = sorted(set(recipe.models) - set(available))

    if len(available) < recipe.min_models:
        return ComposedScore(
            value=None,
            reason=(
                f"only {len(available)} of {len(recipe.models)} models scored this match; "
                f"recipe requires at least {recipe.min_models}"
                + (f" (missing: {', '.join(missing)})" if missing else "")
            ),
        )

    # renormalize: redistribute the missing models' weight proportionally across
    # those present, so the effective weights still sum to 1.
    present_weight = sum(recipe.models[m] for m in available)
    if present_weight <= 0:
        return ComposedScore(value=None, reason="contributing models carry no weight")

    contributors = tuple(
        Contributor(
            model_id=model_id,
            weight=recipe.models[model_id] / present_weight,
            calibrated_score=score.calibrated_score,
        )
        for model_id, score in sorted(available.items())
    )

    value = sum(c.weight * c.calibrated_score for c in contributors)

    return ComposedScore(
        value=round(value, 1),
        reason=(
            f"renormalized over {len(contributors)} of {len(recipe.models)} models "
            f"(missing: {', '.join(missing)})"
            if missing
            else None
        ),
        contributors=contributors,
    )


def compose_all(
    calibrated_by_match: Mapping[str, Sequence[CalibratedScore]],
    recipe: Recipe,
    *,
    match_ids: Iterable[str] | None = None,
) -> dict[str, ComposedScore]:
    """Compose every match. Matches with no scores at all still get an entry, so a
    caller can tell 'no score, and here is why' from 'match not found'."""
    ids = list(match_ids) if match_ids is not None else list(calibrated_by_match)
    return {
        match_id: compose_match(calibrated_by_match.get(match_id, ()), recipe)
        for match_id in ids
    }
