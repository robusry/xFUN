"""The model interface.

Every scoring model implements this and nothing else. The constraints are not
stylistic -- each one buys something specific:

- **Pure.** No network, no database, no filesystem, no clock. All input arrives in
  the snapshot. This is what makes a model testable on fixtures, reproducible
  years later, and runnable in a notebook with nothing else running.

- **Declares its features.** The runtime assembles only what a model asks for and
  skips matches where those are unavailable. A model that needs shot data simply
  produces nothing for leagues without it, rather than blocking the pipeline or
  emitting garbage.

- **Independent.** A model never imports another model and never reads another
  model's output. The moment one does, scoring becomes an ordered graph, backfills
  become sequenced, and composition becomes expensive to reverse.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import MatchSnapshot, ScoreResult

__all__ = ["Model"]


@runtime_checkable
class Model(Protocol):
    """A scoring model."""

    model_id: str
    """Stable kebab-case identifier. Never changes for the life of the model --
    not when it is retuned, not when it is rewritten in another language."""

    model_version: str
    """Semver. MUST be incremented whenever the model produces different output for
    unchanged input. A refactor proven output-identical on fixtures may leave it."""

    required_features: tuple[str, ...]
    """Dotted snapshot paths this model needs, e.g. `("odds.total_line",)`.
    Validated against the snapshot schema at registration: declaring a feature that
    does not exist is a registration error, not a runtime surprise."""

    description: str
    """What signal this model claims to capture. Shown in the public registry."""

    def score(self, snapshot: MatchSnapshot) -> ScoreResult:
        """Score one match.

        Called only when every required feature is present, so implementations do
        not need to defend against missing declared features.

        MUST be deterministic: identical snapshot in, identical result out.
        """
        ...
