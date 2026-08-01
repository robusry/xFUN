"""PLACEHOLDER MODEL. Predicts nothing.

This model exists for two reasons: to demonstrate that models are independent and
fan out in parallel, and to exercise the partial-coverage path. It requires the
three-way moneyline, which the `laliga-2026-08-16-rma-get` fixture deliberately
lacks -- so that match gets scored by one model and not the other, and composition
has to renormalise.

What it computes: the normalised Shannon entropy of the vig-stripped implied
probabilities of home, draw, and away. High entropy means the market cannot
separate the sides, which is a reasonable proxy for a competitive match. Low
entropy means a heavy favourite.

That much is defensible. What makes it a placeholder is that it has never been
validated against any measure of whether such matches were entertaining, and it
ignores goals entirely -- it will rank a tense 0-0 above a 4-3 thriller.

**Replaced by:** the `add-market-baseline-model` change, which folds
competitiveness and goal expectancy into one validated model. See docs/STUBS.md.
"""

from __future__ import annotations

import math

from xfun_contract import MatchSnapshot, ScoreResult

__all__ = ["OddsSpread"]


class OddsSpread:
    """Scores a match by how evenly the market prices the three outcomes."""

    model_id = "odds-spread"
    model_version = "0.1.0"
    required_features = (
        "odds.home_price",
        "odds.draw_price",
        "odds.away_price",
    )
    description = (
        "PLACEHOLDER. Normalised entropy of vig-stripped outcome probabilities. "
        "Ignores goals; unvalidated."
    )

    def score(self, snapshot: MatchSnapshot) -> ScoreResult:
        prices = [
            float(snapshot.feature("odds.home_price")),
            float(snapshot.feature("odds.draw_price")),
            float(snapshot.feature("odds.away_price")),
        ]

        # Decimal odds -> implied probability, then strip the bookmaker's margin
        # so the three sum to 1.
        implied = [1.0 / p for p in prices]
        overround = sum(implied)
        probabilities = [i / overround for i in implied]

        # Normalised Shannon entropy: 1.0 when all three outcomes are equally
        # likely, approaching 0.0 with a heavy favourite.
        entropy = -sum(p * math.log(p) for p in probabilities if p > 0)
        normalised = entropy / math.log(3)

        return ScoreResult(
            raw_score=normalised,
            components={
                "implied_entropy": round(normalised, 4),
                "overround": round(overround, 4),
                "favourite_probability": round(max(probabilities), 4),
            },
        )


MODEL = OddsSpread()
