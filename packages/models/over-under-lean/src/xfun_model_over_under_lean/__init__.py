"""PLACEHOLDER MODEL. Predicts nothing.

This model exists to demonstrate the scoring contract end to end. It reads the
market's over/under goals line and returns it. That is the entire model.

It is not wrong so much as trivial: the over/under line genuinely is the market's
expected goal total, and goals correlate with entertainment. But it ignores
competitiveness entirely, so it will happily rank a 4-0 procession above a tense
1-1, and it has never been validated against any measure of whether matches were
actually enjoyable to watch.

**Replaced by:** the `add-market-baseline-model` change, which builds a real model
over odds -- combining goal expectancy with the competitiveness implied by the
moneyline spread. See docs/STUBS.md.
"""

from __future__ import annotations

from xfun_contract import MatchSnapshot, ScoreResult

__all__ = ["OverUnderLean"]


class OverUnderLean:
    """Scores a match by the market's expected goal total."""

    model_id = "over-under-lean"
    model_version = "0.1.0"
    required_features = ("odds.total_line",)
    description = (
        "PLACEHOLDER. Returns the over/under goals line as the score. "
        "Ignores competitiveness; unvalidated."
    )

    def score(self, snapshot: MatchSnapshot) -> ScoreResult:
        total_line = float(snapshot.feature("odds.total_line"))
        return ScoreResult(
            raw_score=total_line,
            components={"total_line": total_line},
        )


MODEL = OverUnderLean()
