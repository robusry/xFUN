"""How many goals these two sides have been scoring, added together.

NOT A PLACEHOLDER, and not validated either. Every input is real: the goals come from
completed matches that were really played, collected by `recent-results`. What has
never been tested is the hypothesis -- that a match between two sides who have been
scoring is worth watching -- because there is no ground-truth label for "entertaining"
and therefore no way to be shown wrong. `add-evaluation-harness` is the change that
makes this question answerable; until then this model is an argument, not a finding.

What it deliberately ignores, so that nobody has to discover it by reading the code:

- **How close the match is likely to be.** Goals scored says nothing about who scores
  them. Two free-scoring sides heading for a 5-0 procession outrank two mean ones
  heading for a tense 1-1, and this model cannot tell the difference. `odds-spread`
  makes the opposite mistake on purpose.
- **Defence.** Only goals scored count. A side that scores three and concedes four
  looks exactly like one that scores three and keeps clean sheets.
- **Who they were scored against.** Five goals against a relegated side count as five
  goals against the champions, and a cup tie against lower-league opposition counts in
  full.
- **Home and away.** The two totals are added, not weighted, so a 25 + 0 match scores
  the same as a 12 + 13 one. The second is almost certainly the better watch. Left
  alone deliberately: the sum is what the team specified, and a weighting invented here
  would be a second untested hypothesis hidden inside the first.

The scale is the goal total itself -- roughly 5 to 30 -- and it is not normalised,
because models must not normalise. The platform percentile-ranks per (model_id,
model_version) inside a caller-chosen cohort.

A match where either side has fewer than five completed matches carries no value for
that side and is never passed to this model at all; the runtime skips it and records
why. That is routine, not exceptional -- it is most of an August slate.
"""

from __future__ import annotations

from xfun_contract import MatchSnapshot, ScoreResult

__all__ = ["RecentGoalsTotal"]


class RecentGoalsTotal:
    """Scores a match by how many goals its two sides have been scoring lately."""

    model_id = "recent-goals-total"
    model_version = "0.1.0"
    required_features = (
        "signals.form.home.goals_scored_last_5",
        "signals.form.away.goals_scored_last_5",
    )
    description = (
        "Goals scored by each side in its last five completed matches, added "
        "together. Real inputs; validated against nothing."
    )

    def score(self, snapshot: MatchSnapshot) -> ScoreResult:
        home = float(snapshot.feature("signals.form.home.goals_scored_last_5"))
        away = float(snapshot.feature("signals.form.away.goals_scored_last_5"))

        return ScoreResult(
            raw_score=home + away,
            components={
                # Both sides, always, so that a high score is arguable rather than
                # merely asserted: 24 from 12 + 12 is a different match from 24 from
                # 22 + 2, and the composed score cannot tell them apart.
                "home_goals_last_5": home,
                "away_goals_last_5": away,
            },
        )


MODEL = RecentGoalsTotal()
