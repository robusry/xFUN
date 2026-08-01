"""Composition recipes: loading and validation.

A recipe is data, not code. It names models, weights, a missing-model policy, and
a minimum contributing count. Validation is strict on the things that silently
produce nonsense if wrong -- an unknown model_id, or an absent missing-model
policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml

__all__ = [
    "MISSING_POLICIES",
    "IMPLEMENTED_POLICIES",
    "Recipe",
    "RecipeError",
    "PolicyNotImplemented",
    "load_recipe",
    "load_recipes",
    "recipes_dir",
]

MISSING_POLICIES = ("require-all", "renormalize", "fallback")
IMPLEMENTED_POLICIES = frozenset({"renormalize"})


class RecipeError(Exception):
    """A recipe is malformed or references something that does not exist."""


class PolicyNotImplemented(NotImplementedError):
    def __init__(self, policy: str) -> None:
        super().__init__(
            f"Missing-model policy {policy!r} is not implemented in the skeleton. "
            f"Only {sorted(IMPLEMENTED_POLICIES)} is available. "
            f"See docs/STUBS.md -- replaced by complete-composition-policies."
        )
        self.policy = policy


def recipes_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "recipes"


@dataclass(frozen=True)
class Recipe:
    id: str
    version: int
    models: Mapping[str, float]
    on_missing: str
    min_models: int

    @property
    def label(self) -> str:
        return f"{self.id}-v{self.version}"

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "version": self.version,
            "models": dict(self.models),
            "on_missing": self.on_missing,
            "min_models": self.min_models,
        }


def _validate(raw: Mapping[str, object], source: str, known_model_ids: set[str] | None) -> Recipe:
    for key in ("id", "version", "models", "on_missing", "min_models"):
        if key not in raw:
            raise RecipeError(f"{source}: missing required key {key!r}")

    models = raw["models"]
    if not isinstance(models, Mapping) or not models:
        raise RecipeError(f"{source}: 'models' must be a non-empty mapping")

    weights: dict[str, float] = {}
    for model_id, weight in models.items():
        if not isinstance(weight, (int, float)) or weight <= 0:
            raise RecipeError(f"{source}: weight for {model_id!r} must be a positive number")
        weights[str(model_id)] = float(weight)

    policy = raw["on_missing"]
    if policy not in MISSING_POLICIES:
        raise RecipeError(
            f"{source}: on_missing must be one of {MISSING_POLICIES}, got {policy!r}"
        )

    if known_model_ids is not None:
        unknown = sorted(set(weights) - known_model_ids)
        if unknown:
            raise RecipeError(
                f"{source}: references models absent from the registry: {', '.join(unknown)}"
            )

    min_models = raw["min_models"]
    if not isinstance(min_models, int) or min_models < 1:
        raise RecipeError(f"{source}: min_models must be an integer >= 1")

    return Recipe(
        id=str(raw["id"]),
        version=int(raw["version"]),  # type: ignore[arg-type]
        models=weights,
        on_missing=str(policy),
        min_models=min_models,
    )


def load_recipe(path: Path, *, known_model_ids: set[str] | None = None) -> Recipe:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, Mapping):
        raise RecipeError(f"{path.name}: expected a mapping at the top level")
    return _validate(raw, path.name, known_model_ids)


def load_recipes(*, known_model_ids: set[str] | None = None) -> dict[str, Recipe]:
    return {
        recipe.id: recipe
        for recipe in (
            load_recipe(p, known_model_ids=known_model_ids)
            for p in sorted(recipes_dir().glob("*.yaml"))
        )
    }
