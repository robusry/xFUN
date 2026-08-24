"""Reuse of a persisted corpus: when a collector is skipped, and when it is not.

The property that matters here is not "reuse works". It is that reuse never turns
a gap into an answer. A corpus that has never seen an entity must send the run back
to the source, because presenting an unseen entity as one the source had nothing
for is exactly the absence-versus-failure confusion the run record exists to
prevent -- one layer further down, where nothing else would catch it.

The fake corpus is in-memory rather than SQLite on purpose: these tests are about
the invocation DECISION, and the runtime is not allowed to know what a database is.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, ClassVar

import pytest
from xfun_contract import CollectionResult, EntityKind, Slate
from xfun_runtime import CollectorRegistry, run_collectors
from xfun_runtime.paths import fixtures_dir

STAMP = "2026-08-14T04:00:00+00:00"
LATER = "2026-08-14T09:00:00+00:00"  # +5h, inside a 6h window
MUCH_LATER = "2026-08-15T04:00:00+00:00"  # +24h, well outside it


@pytest.fixture
def slate() -> Slate:
    path = fixtures_dir() / "slates" / "2026-08-15-league-allowlist.json"
    return Slate.from_dict(json.loads(path.read_text()))


@dataclass(frozen=True)
class _Entry:
    values: dict[str, dict[str, Any]]
    missing: frozenset[str]


class FakeCorpus:
    """The store's shape, without the store."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict[str, Any]] = {}
        self.stamps: dict[str, str] = {}
        self.writes = 0

    def freshness(self, collector_id: str) -> str | None:
        return self.stamps.get(collector_id)

    def read(self, collector_id: str, entity_ids: Any) -> _Entry:
        asked = list(entity_ids)
        values = {
            eid: self.rows[(collector_id, eid)]
            for eid in asked
            if (collector_id, eid) in self.rows
        }
        return _Entry(values=values, missing=frozenset(set(asked) - set(values)))

    def write(
        self,
        *,
        run_id: str,
        collector_id: str,
        entity_kind: str,
        asked: Any,
        values: Any,
        collected_at: str,
    ) -> None:
        self.writes += 1
        # A row for EVERY asked entity, including the ones with nothing -- the
        # store does the same, and the coverage check depends on it.
        for eid in asked:
            self.rows[(collector_id, eid)] = dict(values.get(eid) or {})
        self.stamps[collector_id] = collected_at


class TeamCollector:
    """Keyed by team, with real partial coverage: two teams of sixteen answer."""

    collector_id = "t-team"
    namespace = "reddit"
    entity_kind = EntityKind.TEAM
    provides = ("excitement",)
    description = "test collector"
    refresh_after_seconds = 6 * 60 * 60
    values: ClassVar[dict] = {"che": {"excitement": 0.81}, "mun": {"excitement": 0.44}}

    def __init__(self) -> None:
        self.calls = 0

    def collect(self, slate: Slate) -> CollectionResult:
        self.calls += 1
        return CollectionResult(values=self.values)


class AlwaysCollector(TeamCollector):
    """Declares no cadence, so nothing licenses calling its output fresh."""

    collector_id = "t-always"
    refresh_after_seconds = None


class FailingCollector(TeamCollector):
    collector_id = "t-failing"

    def collect(self, slate: Slate) -> CollectionResult:
        self.calls += 1
        return CollectionResult.unavailable("HTTP 503")


def _run(collector, corpus, slate, stamp, force=False):
    registry = CollectorRegistry()
    registry.register(collector)
    return run_collectors(
        registry,
        slate,
        registry.provided_paths(),
        run_id="test",
        started_at=stamp,
        corpus=corpus,
        force=force,
    )


def _outcome(run, collector_id):
    return next(o for o in run.outcomes if o.collector_id == collector_id)


def test_fresh_and_complete_corpus_skips_the_source(slate):
    corpus, collector = FakeCorpus(), TeamCollector()

    first = _run(collector, corpus, slate, STAMP)
    assert collector.calls == 1
    assert _outcome(first, "t-team").outcome == "succeeded"

    second = _run(collector, corpus, slate, LATER)
    assert collector.calls == 1, "the source was contacted again despite a fresh corpus"

    outcome = _outcome(second, "t-team")
    assert outcome.outcome == "reused"
    assert outcome.entities_with_data == 2
    assert second.signals == first.signals, "reuse changed what models will see"


def test_a_corpus_missing_one_slate_entity_still_collects(slate):
    """The check that keeps a gap from being served as an answer."""
    corpus, collector = FakeCorpus(), TeamCollector()
    _run(collector, corpus, slate, STAMP)
    assert collector.calls == 1

    # Forget one team. The corpus is still well inside its refresh window.
    forgotten = next(eid for (cid, eid) in corpus.rows if cid == "t-team")
    del corpus.rows[("t-team", forgotten)]

    run = _run(collector, corpus, slate, LATER)
    assert collector.calls == 2, "a corpus with a hole in it was treated as complete"
    assert _outcome(run, "t-team").outcome == "succeeded"


def test_an_entity_the_source_had_nothing_for_still_counts_as_covered(slate):
    """Stored `{}` is coverage, not a hole.

    Fourteen of sixteen teams get an empty row on the first run. If those did not
    count as covered, this collector could never be reused and the whole feature
    would be dead code for every partial-coverage source -- which is most of them.
    """
    corpus, collector = FakeCorpus(), TeamCollector()
    _run(collector, corpus, slate, STAMP)

    empty = [eid for (cid, eid), v in corpus.rows.items() if cid == "t-team" and not v]
    assert len(empty) == len(slate.teams()) - 2

    run = _run(collector, corpus, slate, LATER)
    assert collector.calls == 1
    assert _outcome(run, "t-team").outcome == "reused"


def test_a_corpus_past_its_window_collects_again(slate):
    corpus, collector = FakeCorpus(), TeamCollector()
    _run(collector, corpus, slate, STAMP)

    run = _run(collector, corpus, slate, MUCH_LATER)
    assert collector.calls == 2
    assert _outcome(run, "t-team").outcome == "succeeded"


def test_no_declared_window_means_collect_every_run(slate):
    corpus, collector = FakeCorpus(), AlwaysCollector()
    _run(collector, corpus, slate, STAMP)
    _run(collector, corpus, slate, STAMP)
    assert collector.calls == 2


def test_failure_neither_writes_nor_consumes_the_corpus(slate):
    """A failed collector leaves the last good corpus alone and does not serve it."""
    corpus = FakeCorpus()
    good, bad = TeamCollector(), FailingCollector()

    # Seed a corpus under the failing collector's own id, so the only reason not
    # to serve it is the policy under test.
    _run(good, corpus, slate, STAMP)
    corpus.rows.update(
        {("t-failing", eid): v for (cid, eid), v in corpus.rows.items() if cid == "t-team"}
    )
    corpus.stamps["t-failing"] = STAMP
    before = dict(corpus.rows)

    run = _run(bad, corpus, slate, MUCH_LATER)

    outcome = _outcome(run, "t-failing")
    assert outcome.outcome == "failed"
    assert outcome.reason == "HTTP 503"
    assert run.signals == {}, "stale values were served in place of a failure"
    assert corpus.rows == before, "a failed collection overwrote a good corpus"
    assert "reddit" in str(run.unavailable_paths()), "the skip is not attributable to failure"


def test_a_recovered_source_supersedes(slate):
    corpus = FakeCorpus()
    bad = FailingCollector()
    _run(bad, corpus, slate, STAMP)
    assert corpus.writes == 0

    class Recovered(FailingCollector):
        def collect(self, slate: Slate) -> CollectionResult:
            return CollectionResult(values={"che": {"excitement": 0.9}})

    run = _run(Recovered(), corpus, slate, LATER)
    assert _outcome(run, "t-failing").outcome == "succeeded"
    assert corpus.rows[("t-failing", "che")] == {"excitement": 0.9}


def test_force_collects_despite_a_fresh_corpus(slate):
    corpus, collector = FakeCorpus(), TeamCollector()
    _run(collector, corpus, slate, STAMP)

    run = _run(collector, corpus, slate, LATER, force=True)
    assert collector.calls == 2
    assert _outcome(run, "t-team").outcome == "succeeded"
    assert corpus.rows[("t-team", "che")] == {"excitement": 0.81}, "forcing lost data"


def test_no_corpus_at_all_behaves_as_before(slate):
    """Omitting the corpus restores pre-persistence behaviour exactly."""
    collector = TeamCollector()
    _run(collector, None, slate, STAMP)
    _run(collector, None, slate, STAMP)
    assert collector.calls == 2


def test_the_decision_does_not_depend_on_when_the_test_runs(slate):
    """The reproducibility property freshness-by-injected-stamp exists to protect.

    Same inputs and same stamp, twice, must produce the same invocation decision.
    A freshness check that read the clock would pass this only by luck.
    """
    corpus, collector = FakeCorpus(), TeamCollector()
    _run(collector, corpus, slate, STAMP)

    first = _run(collector, corpus, slate, LATER)
    calls_after_first = collector.calls
    second = _run(collector, corpus, slate, LATER)

    assert collector.calls == calls_after_first
    assert _outcome(first, "t-team").to_dict() == _outcome(second, "t-team").to_dict()


def test_a_corpus_stamped_in_the_future_is_not_treated_as_fresh(slate):
    """Replaying an older run must not pull a newer run's data backwards."""
    corpus, collector = FakeCorpus(), TeamCollector()
    _run(collector, corpus, slate, MUCH_LATER)

    run = _run(collector, corpus, slate, STAMP)
    assert collector.calls == 2
    assert _outcome(run, "t-team").outcome == "succeeded"
