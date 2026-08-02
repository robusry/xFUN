"""The collector registry, resolution, and the run record.

Three things happen here, and each exists to make a specific failure loud.

**Registration** rejects two producers claiming one signal path. Without that check
the winner would be whichever registered last, and a model would read a value from
a collector it never intended -- with no symptom.

**Resolution** works out which collectors a run actually needs, from the union of
what the active models declared. A source nothing consumes is not fetched: network
cost and rate limits are real, and paying them for data no model reads is waste
that never shows up as an error.

**The run record** captures what happened, including the distinction between a
collector that failed and one that succeeded and had nothing. Those two produce an
identical absence in the snapshot, so if the record does not separate them, nothing
downstream can either -- and a source that was down for a week looks exactly like a
source with nothing to say.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from xfun_contract import CollectionResult, Collector, EntityKind, Slate

from .join import entity_ids, expand_paths, join_values, merge_signals

__all__ = [
    "CollectionRun",
    "CollectorOutcome",
    "CollectorRegistrationError",
    "CollectorRegistry",
    "run_collectors",
]

_ID_PATTERN = re.compile(r"^[a-z0-9-]+$")


class CollectorRegistrationError(Exception):
    """A collector's declarations are inconsistent with the contract, or collide
    with another collector's."""


@dataclass(frozen=True)
class RegisteredCollector:
    collector: Collector
    paths: tuple[str, ...]
    """The expanded full paths this collector's leaves resolve to after joining."""

    @property
    def collector_id(self) -> str:
        return self.collector.collector_id


class CollectorRegistry:
    """Holds the collectors a run may draw on, and who provides what."""

    def __init__(self) -> None:
        self._collectors: dict[str, RegisteredCollector] = {}
        self._providers: dict[str, str] = {}

    def register(self, collector: Collector) -> None:
        if not _ID_PATTERN.match(collector.collector_id):
            raise CollectorRegistrationError(
                f"collector_id {collector.collector_id!r} must be kebab-case: [a-z0-9-]+"
            )
        if collector.collector_id in self._collectors:
            raise CollectorRegistrationError(
                f"collector_id {collector.collector_id!r} is already registered"
            )
        if not _ID_PATTERN.match(collector.namespace):
            raise CollectorRegistrationError(
                f"{collector.collector_id}: namespace {collector.namespace!r} must be "
                f"kebab-case: [a-z0-9-]+"
            )
        if not collector.provides:
            raise CollectorRegistrationError(
                f"{collector.collector_id}: must declare at least one provided leaf"
            )
        kind = EntityKind(collector.entity_kind)

        paths = expand_paths(collector.namespace, tuple(collector.provides), kind)

        # A namespace is a subject area rather than a producer, so two collectors
        # may share one. What must never be shared is a leaf path: that is the
        # thing a model names, and it must resolve to exactly one producer.
        for path in paths:
            owner = self._providers.get(path)
            if owner is not None:
                raise CollectorRegistrationError(
                    f"{collector.collector_id}: path {path!r} is already provided by "
                    f"{owner!r}. Exactly one producer may claim a path."
                )

        self._collectors[collector.collector_id] = RegisteredCollector(
            collector=collector, paths=paths
        )
        for path in paths:
            self._providers[path] = collector.collector_id

    def provided_paths(self) -> frozenset[str]:
        """Every signal path some registered collector provides."""
        return frozenset(self._providers)

    def provider_of(self, path: str) -> str | None:
        return self._providers.get(path)

    def required_for(self, paths: Iterable[str]) -> tuple[RegisteredCollector, ...]:
        """The collectors needed to satisfy these declared paths, in stable order.

        Deduplicated: three models declaring paths from one collector yield that
        collector once, which is the whole point of the tier.
        """
        needed = {
            self._providers[path] for path in paths if path in self._providers
        }
        return tuple(
            self._collectors[cid] for cid in sorted(needed)
        )

    def all(self) -> tuple[RegisteredCollector, ...]:
        return tuple(self._collectors[cid] for cid in sorted(self._collectors))

    def get(self, collector_id: str) -> RegisteredCollector | None:
        return self._collectors.get(collector_id)

    def __len__(self) -> int:
        return len(self._collectors)

    def __contains__(self, collector_id: object) -> bool:
        return collector_id in self._collectors


@dataclass(frozen=True)
class CollectorOutcome:
    """How one collector fared on one run."""

    collector_id: str
    entity_kind: str
    outcome: str
    """`succeeded`, `failed`, or `not_invoked`. See contracts/schemas/collection-run.json."""
    provides: tuple[str, ...] = ()
    reason: str | None = None
    entities_with_data: int | None = None
    entities_without_data: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "collector_id": self.collector_id,
            "entity_kind": self.entity_kind,
            "outcome": self.outcome,
        }
        if self.provides:
            out["provides"] = list(self.provides)
        if self.reason is not None:
            out["reason"] = self.reason
        if self.entities_with_data is not None:
            out["entities_with_data"] = self.entities_with_data
        if self.entities_without_data is not None:
            out["entities_without_data"] = self.entities_without_data
        return out


@dataclass
class CollectionRun:
    """What one collection run did, and what it produced."""

    run_id: str
    slate_id: str
    started_at: str
    completed_at: str | None = None
    outcomes: list[CollectorOutcome] = field(default_factory=list)
    signals: dict[str, dict[str, Any]] = field(default_factory=dict)
    """match_id -> {namespace -> payload}. Joined onto matches, ready to be folded
    into a snapshot. Not persisted: snapshots are assembled per run, so signals
    inherit that -- see docs/STUBS.md and `add-score-provenance`."""

    def failed_collectors(self) -> tuple[str, ...]:
        return tuple(o.collector_id for o in self.outcomes if o.outcome == "failed")

    def unavailable_paths(self) -> dict[str, str]:
        """Feature path -> why its source could not answer, for failed collectors.

        Handed to `run_models` so a skip can say whether the data was absent or
        merely unestablished. Only failures appear here: a collector that succeeded
        and returned nothing produced real coverage information, not a gap.
        """
        return {
            path: f"collector {outcome.collector_id!r} failed: {outcome.reason}"
            for outcome in self.outcomes
            if outcome.outcome == "failed"
            for path in outcome.provides
        }

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for outcome in self.outcomes:
            counts[outcome.outcome] = counts.get(outcome.outcome, 0) + 1
        parts = [f"{n} {name}" for name, n in sorted(counts.items())]
        return f"{len(self.signals)} matches with signals, {', '.join(parts) or 'no collectors'}"

    def to_dict(self) -> dict[str, Any]:
        """Conforms to contracts/schemas/collection-run.json."""
        out: dict[str, Any] = {
            "run_id": self.run_id,
            "slate_id": self.slate_id,
            "started_at": self.started_at,
            "collectors": [o.to_dict() for o in self.outcomes],
        }
        if self.completed_at is not None:
            out["completed_at"] = self.completed_at
        return out


def run_collectors(
    registry: CollectorRegistry,
    slate: Slate,
    required_paths: Iterable[str],
    *,
    run_id: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
) -> CollectionRun:
    """Collect everything the declared paths need, once each, and record it.

    `run_id` and the timestamps are injected rather than read from the clock, for
    the same reason `run_models` injects `computed_at`: a run that reads the clock
    itself cannot be reproduced in a test.
    """
    stamp = started_at or datetime.now(UTC).isoformat(timespec="seconds")
    identifier = run_id or f"run-{stamp.replace(':', '-')}"

    required = set(required_paths)
    needed = {rc.collector_id for rc in registry.required_for(required)}

    run = CollectionRun(run_id=identifier, slate_id=slate.slate_id, started_at=stamp)

    for registered in registry.all():
        collector = registered.collector
        kind = EntityKind(collector.entity_kind)

        if registered.collector_id not in needed:
            # Not an error and not a failure: nothing declared anything it
            # provides, so not calling it is correct behaviour worth recording.
            run.outcomes.append(
                CollectorOutcome(
                    collector_id=registered.collector_id,
                    entity_kind=str(kind),
                    outcome="not_invoked",
                    provides=registered.paths,
                )
            )
            continue

        asked = entity_ids(slate, kind)

        try:
            result = collector.collect(slate)
        except Exception as exc:  # noqa: BLE001 - any escape is a failure to determine
            # A collector that raises has not established that data is absent, so
            # this must not be recorded as coverage.
            result = CollectionResult.unavailable(f"{type(exc).__name__}: {exc}")

        if result.failed:
            run.outcomes.append(
                CollectorOutcome(
                    collector_id=registered.collector_id,
                    entity_kind=str(kind),
                    outcome="failed",
                    provides=registered.paths,
                    reason=result.failure,
                )
            )
            continue

        answered = {eid for eid in asked if result.values.get(eid)}
        merge_signals(
            run.signals,
            collector.namespace,
            join_values(slate, kind, result.values),
        )

        run.outcomes.append(
            CollectorOutcome(
                collector_id=registered.collector_id,
                entity_kind=str(kind),
                outcome="succeeded",
                provides=registered.paths,
                entities_with_data=len(answered),
                entities_without_data=len(asked) - len(answered),
            )
        )

    run.completed_at = completed_at
    return run


def apply_signals(
    payload: Mapping[str, Any],
    signals: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Fold a match's collected signals into its snapshot payload.

    Done before hashing, so that a change in a collected signal produces a
    different `snapshot_hash` and therefore a new score row -- which is what makes
    a chatty collector's cost visible rather than silent.
    """
    merged = dict(payload)
    namespaces = signals.get(payload["match_id"])
    if namespaces:
        merged["signals"] = {ns: dict(values) for ns, values in namespaces.items()}
    return merged
