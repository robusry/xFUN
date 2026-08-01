"""Request context: store access, recipes, and alias resolution.

Kept separate from the routes so the routes read as what they are -- thin
translations between HTTP and arithmetic over stored rows.

Note what this module does NOT do: import a model, or execute one. Everything it
knows about models comes from the `model_registry` table, written by the scoring
run. That is what lets the API keep serving when every model package is broken.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from xfun_composition import (
    Alias,
    AliasResolver,
    ComposedScore,
    Contributor,
    Recipe,
    compose_match,
    load_recipes,
)
from xfun_contract import MatchSnapshot, ModelScore
from xfun_runtime.calibration import CalibratedScore
from xfun_store import connect, latest_scores, load_snapshots

__all__ = ["ApiContext", "get_context"]


@dataclass
class ApiContext:
    recipes: dict[str, Recipe]
    aliases: AliasResolver

    # ---- store reads -------------------------------------------------------

    def _conn(self):
        return connect()

    def snapshots(
        self, *, date_from: str | None = None, date_to: str | None = None
    ) -> tuple[MatchSnapshot, ...]:
        with self._conn() as conn:
            return load_snapshots(conn, date_from=date_from, date_to=date_to)

    def snapshot(self, match_id: str) -> MatchSnapshot | None:
        for snapshot in self.snapshots():
            if snapshot.match_id == match_id:
                return snapshot
        return None

    def scores(self, match_ids: Sequence[str] | None = None) -> tuple[ModelScore, ...]:
        with self._conn() as conn:
            return latest_scores(conn, match_ids=match_ids)

    def registered_models(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM model_registry ORDER BY model_id"
            ).fetchall()
        return [
            {
                "model_id": r["model_id"],
                "model_version": r["model_version"],
                "description": r["description"],
                "retired": bool(r["retired"]),
                "required_features": json.loads(r["features"]),
            }
            for r in rows
        ]

    # ---- composition -------------------------------------------------------

    def recipe_for(self, target: Alias) -> Recipe | None:
        return self.aliases.recipe_for(target.alias)

    def compose(
        self,
        scores: Sequence[CalibratedScore],
        target: Alias,
        recipe: Recipe | None,
    ) -> ComposedScore:
        """Compose under a recipe, or pass a single model's score straight through.

        Aliases pointing at one model take the same path as composed aliases, which
        is what makes "expose a model" and "expose a blend" one code path.
        """
        if recipe is not None:
            return compose_match(scores, recipe)

        for score in scores:
            if score.model_id == target.resolves_to:
                return ComposedScore(
                    value=score.calibrated_score,
                    contributors=(
                        Contributor(
                            model_id=score.model_id,
                            weight=1.0,
                            calibrated_score=score.calibrated_score,
                        ),
                    ),
                )
        return ComposedScore(
            value=None,
            reason=f"model {target.resolves_to!r} did not score this match",
        )


@lru_cache(maxsize=1)
def _build_context() -> ApiContext:
    with connect() as conn:
        known = {
            r["model_id"]
            for r in conn.execute("SELECT model_id FROM model_registry")
        }
    recipes = load_recipes(known_model_ids=known or None)
    return ApiContext(
        recipes=recipes,
        aliases=AliasResolver(recipes, model_ids={m: m for m in known}),
    )


def get_context() -> ApiContext:
    return _build_context()
