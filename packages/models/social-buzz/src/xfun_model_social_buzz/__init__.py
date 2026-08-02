"""PLACEHOLDER MODEL. Predicts nothing.

This model exists to make the collector tier reachable end to end. The other two
models read odds, which ingestion writes directly as canonical entities; this one
reads `signals.*`, which exists only because a collector produced it and the
platform joined it onto the match.

Note what it does NOT do. It never imports a collector, never knows which collector
produced which value, and never learns whether `signals.reddit.home.excitement`
arrived from one source or three. It declares two dotted paths. That indirection is
the entire point of the tier: the producer behind a path can be replaced without
this file changing, which is why provenance is recorded in the run record rather
than encoded in the path.

What it computes: mentions multiplied by the home following's apparent interest. The
scale is arbitrary -- in the hundreds -- and deliberately so. Models MUST NOT
normalise; the platform percentile-ranks per (model_id, model_version) within a
caller-chosen cohort.

What makes it a placeholder is that the arithmetic is invented and the signals
feeding it are invented too. A heavily-discussed match between two dull teams
outranks a quiet thriller, and the away side is ignored entirely -- because the
fixture data covers one side on purpose, to keep the partial-coverage path honest.

**Replaced by:** whichever change first builds a validated model over social
signals. See docs/STUBS.md.
"""

from __future__ import annotations

import math

from xfun_contract import MatchSnapshot, ScoreResult

__all__ = ["SocialBuzz"]


class SocialBuzz:
    """Scores a match by how much attention it appears to be getting."""

    model_id = "social-buzz"
    model_version = "0.1.0"
    required_features = (
        "signals.match-buzz.mentions",
        "signals.reddit.home.excitement",
    )
    description = (
        "PLACEHOLDER. Mentions weighted by the home following's interest. Both "
        "inputs are invented; validated against nothing."
    )

    def score(self, snapshot: MatchSnapshot) -> ScoreResult:
        mentions = float(snapshot.feature("signals.match-buzz.mentions"))
        excitement = float(snapshot.feature("signals.reddit.home.excitement"))

        # Log-damped, because raw mention counts are heavy-tailed and one viral
        # match would otherwise dominate every cohort it appears in. This is a
        # defensible shape applied to indefensible inputs.
        attention = math.log1p(mentions) * excitement

        return ScoreResult(
            raw_score=attention,
            components={
                "mentions": round(mentions, 4),
                "home_excitement": round(excitement, 4),
                "log_attention": round(attention, 4),
            },
        )


MODEL = SocialBuzz()
