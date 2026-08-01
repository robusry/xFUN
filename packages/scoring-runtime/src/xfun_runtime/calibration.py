"""Turning incomparable raw scores into comparable ones.

Models emit raw scores on whatever native scale suits them -- a probability, a
z-score, an arbitrary index. Averaging those directly produces plausible nonsense,
so the platform percentile-ranks each model's raw scores within a cohort to yield a
0-100 value. Ranking is per (model_id, model_version): a model is only ever
compared against itself.

**The cohort is chosen by the caller, per request.** That is why a calibrated score
is never stored: the same raw score yields different calibrated values under
different cohorts. `window` answers "best of what's on this weekend"; `season`
answers "best of the season". Both are legitimate and they disagree, which is
exactly why every response must state which cohort produced it.

Only `window` is implemented in the skeleton. See docs/STUBS.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from xfun_contract import ModelScore

__all__ = [
    "COHORT_DEFINITIONS",
    "IMPLEMENTED_COHORTS",
    "MIN_COHORT_SIZE",
    "CohortInfo",
    "CohortNotImplemented",
    "CalibratedScore",
    "CalibrationResult",
    "calibrate",
    "resolve_cohort",
]

COHORT_DEFINITIONS = ("window", "league", "season", "global")
IMPLEMENTED_COHORTS = frozenset({"window"})

MIN_COHORT_SIZE = 3
"""Below this, a percentile rank says more about the cohort than the match.
Results are still returned, marked low_confidence, rather than withheld -- an
honest weak signal beats a gap. Widening-fallback is deferred; see docs/STUBS.md."""


class CohortNotImplemented(NotImplementedError):
    """A valid cohort definition that this build does not implement yet."""

    def __init__(self, definition: str) -> None:
        super().__init__(
            f"Calibration cohort {definition!r} is not implemented in the skeleton. "
            f"Only {sorted(IMPLEMENTED_COHORTS)} is available. "
            f"See docs/STUBS.md -- replaced by the complete-calibration-cohorts change."
        )
        self.definition = definition


@dataclass(frozen=True)
class CohortInfo:
    """A calibrated score without this is uninterpretable, so it travels with it."""

    definition: str
    match_count: int
    low_confidence: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "definition": self.definition,
            "match_count": self.match_count,
            "low_confidence": self.low_confidence,
        }


@dataclass(frozen=True)
class CalibratedScore:
    match_id: str
    model_id: str
    model_version: str
    raw_score: float
    calibrated_score: float
    components: Mapping[str, float]


@dataclass(frozen=True)
class CalibrationResult:
    scores: tuple[CalibratedScore, ...]
    cohort: CohortInfo

    def by_match(self) -> dict[str, list[CalibratedScore]]:
        out: dict[str, list[CalibratedScore]] = {}
        for score in self.scores:
            out.setdefault(score.match_id, []).append(score)
        return out


def resolve_cohort(
    definition: str,
    scores: Sequence[ModelScore],
    *,
    league_of: Mapping[str, str] | None = None,
) -> dict[str, list[ModelScore]]:
    """Group scores into cohorts.

    `window` puts every score in the requested range into one cohort -- matches are
    ranked against everything else on offer in that window.
    """
    if definition not in COHORT_DEFINITIONS:
        raise ValueError(
            f"Unknown cohort {definition!r}. Expected one of {COHORT_DEFINITIONS}."
        )
    if definition not in IMPLEMENTED_COHORTS:
        raise CohortNotImplemented(definition)

    return {"window": list(scores)}


def _percentile_rank(value: float, population: Sequence[float]) -> float:
    """Percent of the population at or below `value`, tie-aware.

    Uses the midpoint convention for ties, so identical raw scores calibrate
    identically instead of being separated by arbitrary ordering.
    """
    n = len(population)
    if n == 0:
        return 50.0
    if n == 1:
        return 50.0
    below = sum(1 for other in population if other < value)
    equal = sum(1 for other in population if other == value)
    return 100.0 * (below + 0.5 * equal) / n


def calibrate(
    scores: Iterable[ModelScore],
    *,
    cohort: str = "window",
    league_of: Mapping[str, str] | None = None,
) -> CalibrationResult:
    """Percentile-rank raw scores to 0-100 within the chosen cohort.

    Ranking happens per (model_id, model_version) inside each cohort, so a model is
    never ranked against a different model or against its own earlier version.
    """
    scores = list(scores)
    groups = resolve_cohort(cohort, scores, league_of=league_of)

    calibrated: list[CalibratedScore] = []
    match_ids: set[str] = set()

    for cohort_scores in groups.values():
        populations: dict[tuple[str, str], list[float]] = {}
        for score in cohort_scores:
            key = (score.model_id, score.model_version)
            populations.setdefault(key, []).append(score.raw_score)

        for score in cohort_scores:
            key = (score.model_id, score.model_version)
            calibrated.append(
                CalibratedScore(
                    match_id=score.match_id,
                    model_id=score.model_id,
                    model_version=score.model_version,
                    raw_score=score.raw_score,
                    calibrated_score=round(
                        _percentile_rank(score.raw_score, populations[key]), 1
                    ),
                    components=score.components,
                )
            )
            match_ids.add(score.match_id)

    return CalibrationResult(
        scores=tuple(calibrated),
        cohort=CohortInfo(
            definition=cohort,
            match_count=len(match_ids),
            low_confidence=len(match_ids) < MIN_COHORT_SIZE,
        ),
    )
