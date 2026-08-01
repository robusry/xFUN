"""Score aliases: stable public names over volatile bindings.

Consumers address `default`, never `default-v3`. Repointing an alias changes what
everyone receives with no client change and no contract change -- the same
indirection as a Docker tag or a DNS record.

The same mechanism makes "expose one model" and "expose a blend" the same code
path with different targets, which is what lets the composition decision stay
deferrable indefinitely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from .recipe import Recipe

__all__ = ["Alias", "AliasResolver", "AliasNotFound"]


class AliasNotFound(KeyError):
    def __init__(self, alias: str, known: list[str]) -> None:
        super().__init__(
            f"Unknown score alias {alias!r}. Known aliases: {', '.join(sorted(known))}."
        )
        self.alias = alias


@dataclass(frozen=True)
class Alias:
    alias: str
    kind: Literal["composition", "model"]
    resolves_to: str

    def to_dict(self) -> dict[str, str]:
        return {"alias": self.alias, "kind": self.kind, "resolves_to": self.resolves_to}


class AliasResolver:
    """Maps public alias names onto compositions or single models.

    `default` always exists. Aliases pointing at a single model let a consumer take
    one model's calibrated score straight through, and let third parties build
    their own blends from per-model scores.
    """

    def __init__(
        self,
        recipes: Mapping[str, Recipe],
        *,
        model_ids: Mapping[str, str] | None = None,
    ) -> None:
        self._recipes = dict(recipes)
        self._aliases: dict[str, Alias] = {}

        for recipe_id, recipe in self._recipes.items():
            self._aliases[recipe_id] = Alias(recipe_id, "composition", recipe.label)
            # A pinned target that is never repointed, for consumers needing
            # determinism across time.
            self._aliases[recipe.label] = Alias(recipe.label, "composition", recipe.label)

        for model_id in (model_ids or {}):
            self._aliases.setdefault(model_id, Alias(model_id, "model", model_id))

        if "default" not in self._aliases:
            raise ValueError("the 'default' alias must always exist")

    def resolve(self, alias: str) -> Alias:
        try:
            return self._aliases[alias]
        except KeyError:
            raise AliasNotFound(alias, list(self._aliases)) from None

    def recipe_for(self, alias: str) -> Recipe | None:
        """The recipe an alias resolves to, or None when it points at a model."""
        target = self.resolve(alias)
        if target.kind != "composition":
            return None
        for recipe in self._recipes.values():
            if recipe.label == target.resolves_to:
                return recipe
        return None

    def all(self) -> tuple[Alias, ...]:
        return tuple(self._aliases.values())
