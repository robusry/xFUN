"""What a model declares it needs.

Today there is exactly one kind of declaration: dotted feature paths, whose
coverage the PLATFORM decides -- the runtime checks the paths are present and skips
the match if they are not, so the model is never invoked without them.

This module exists so that is not the only kind there can ever be. A declaration
whose coverage the MODEL decides is already anticipated: given a corpus of posts,
only the model can say whether two of them are enough to score on. That kind needs
a way for `score` to decline, which the current contract has no room for.

Rather than close the mechanism now and amend it later, requirements are read
through `declared_requirements`, which knows how to find every kind a model may
declare. Adding a kind means adding a dataclass here and a branch there -- not
rewriting the requirement that says models declare what they need.

See the `add-collector-corpora` change for the kind this was left open for.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["FeaturePaths", "Requirement", "declared_feature_paths", "declared_requirements"]


@dataclass(frozen=True)
class FeaturePaths:
    """Dotted snapshot paths the model needs present before it is invoked.

    Coverage is decided by the platform: every path present, or the match is
    skipped with a recorded reason and `score` is never called.
    """

    paths: tuple[str, ...]


#: The union of declaration kinds. Grows; nothing may assume it is a single type.
Requirement = FeaturePaths


def declared_requirements(model: object) -> tuple[Requirement, ...]:
    """Every requirement a model declares, in whatever kinds it used.

    Reads `required_features` today. When a further kind is added, this is where it
    is recognised, so that callers iterating requirements keep working unchanged.
    """
    requirements: list[Requirement] = []

    paths = tuple(getattr(model, "required_features", ()) or ())
    if paths:
        requirements.append(FeaturePaths(paths=paths))

    return tuple(requirements)


def declared_feature_paths(model: object) -> tuple[str, ...]:
    """Just the dotted paths, for callers that only care about those.

    Separate from `declared_requirements` so that adding a kind does not silently
    change what this returns -- a caller wanting paths should keep getting paths.
    """
    return tuple(
        path
        for requirement in declared_requirements(model)
        if isinstance(requirement, FeaturePaths)
        for path in requirement.paths
    )
