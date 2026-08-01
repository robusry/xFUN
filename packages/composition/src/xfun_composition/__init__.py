"""Versioned composition recipes and repointable score aliases.

The recipes are configuration; this package is the mechanism that reads them.
That split is deliberate: the mechanism is Zone A and always requires specs, the
recipe values are Zone C and change freely.
"""

from .aliases import Alias, AliasNotFound, AliasResolver
from .compose import ComposedScore, Contributor, compose_all, compose_match
from .recipe import (
    IMPLEMENTED_POLICIES,
    MISSING_POLICIES,
    PolicyNotImplemented,
    Recipe,
    RecipeError,
    load_recipe,
    load_recipes,
    recipes_dir,
)

__all__ = [
    "IMPLEMENTED_POLICIES",
    "MISSING_POLICIES",
    "Alias",
    "AliasNotFound",
    "AliasResolver",
    "ComposedScore",
    "Contributor",
    "PolicyNotImplemented",
    "Recipe",
    "RecipeError",
    "compose_all",
    "compose_match",
    "load_recipe",
    "load_recipes",
    "recipes_dir",
]
