"""The model runner: fan out registered models over snapshots.

Two properties matter more than anything else here.

**Order independence.** Models never read each other's output, so the runner may
execute them in any order, or in parallel, and produce identical results. If that
ever stops being true, a model has reached outside its snapshot.

**Skips are recorded, not swallowed.** A model with unavailable features produces
no score for that match, and the reason is captured. Silence would be
indistinguishable from a model that ran and returned nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from xfun_contract import MatchSnapshot, ModelScore

from .registry import Registry

__all__ = ["RunResult", "Skip", "run_models"]


@dataclass(frozen=True)
class Skip:
    """A model did not score a match, and why.

    The two ways a feature can be missing are NOT interchangeable. Absent data is a
    permanent, correct answer about this match. A collector that failed established
    nothing at all, and the same match may well be scoreable on the next run. They
    produce an identical hole in the snapshot, so if the skip does not separate
    them, nothing downstream can.
    """

    match_id: str
    model_id: str
    missing_features: tuple[str, ...]
    failures: Mapping[str, str] = field(default_factory=dict)
    """Missing path -> why its source could not answer. Empty when the data is
    simply absent."""

    @property
    def caused_by_failure(self) -> bool:
        return bool(self.failures)

    @property
    def reason(self) -> str:
        missing = ", ".join(self.missing_features)
        if not self.failures:
            return f"missing required features: {missing}"
        causes = "; ".join(f"{path} ({why})" for path, why in sorted(self.failures.items()))
        return f"missing required features: {missing} — source unavailable: {causes}"


@dataclass
class RunResult:
    scores: list[ModelScore] = field(default_factory=list)
    skips: list[Skip] = field(default_factory=list)

    def summary(self) -> str:
        return f"{len(self.scores)} scores, {len(self.skips)} skips"


def run_models(
    registry: Registry,
    snapshots: Iterable[MatchSnapshot],
    *,
    computed_at: str | None = None,
    unavailable: Mapping[str, str] | None = None,
) -> RunResult:
    """Score every snapshot with every active model that can score it.

    `computed_at` is injected rather than read from the clock inside a model,
    because models must be deterministic. The runner is where time enters.

    `unavailable` maps a feature path to why its source could not answer this run,
    as reported by the collection run. It changes no scoring decision -- a missing
    feature is a skip either way -- but it is what lets the recorded skip say which
    kind of missing it was.
    """
    stamp = computed_at or datetime.now(UTC).isoformat(timespec="seconds")
    unreachable = dict(unavailable or {})
    result = RunResult()

    for snapshot in snapshots:
        snapshot_hash = snapshot.hash

        for registered in registry.active():
            model = registered.model
            missing = snapshot.missing_features(model.required_features)

            if missing:
                result.skips.append(
                    Skip(
                        match_id=snapshot.match_id,
                        model_id=model.model_id,
                        missing_features=missing,
                        failures={
                            path: unreachable[path] for path in missing if path in unreachable
                        },
                    )
                )
                continue

            outcome = model.score(snapshot)
            result.scores.append(
                ModelScore(
                    match_id=snapshot.match_id,
                    model_id=model.model_id,
                    model_version=model.model_version,
                    raw_score=float(outcome.raw_score),
                    components={k: float(v) for k, v in outcome.components.items()},
                    snapshot_hash=snapshot_hash,
                    computed_at=stamp,
                )
            )

    return result
