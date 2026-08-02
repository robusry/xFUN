"""Collection: resolution, the entity joins, and honest failure reporting.

The properties under test are the ones that would fail silently if they broke. A
collector fetched three times instead of once still produces correct scores, and
nothing complains until a rate limit does. A failed collector recorded as absence
still produces correct-looking output, and nothing complains ever.
"""

from __future__ import annotations

import json
from typing import ClassVar

import pytest
from xfun_contract import CollectionResult, EntityKind, MatchSnapshot, ScoreResult, Slate
from xfun_runtime import (
    CollectorRegistrationError,
    CollectorRegistry,
    RegistrationError,
    Registry,
    run_collectors,
    run_models,
)
from xfun_runtime.paths import fixtures_dir


@pytest.fixture
def slate() -> Slate:
    path = fixtures_dir() / "slates" / "2026-08-15-league-allowlist.json"
    return Slate.from_dict(json.loads(path.read_text()))


class _Recording:
    """Base for test collectors: counts how many times it was invoked."""

    description = "test collector"
    refresh_after_seconds = None

    def __init__(self) -> None:
        self.calls = 0

    def collect(self, slate: Slate) -> CollectionResult:
        self.calls += 1
        return CollectionResult(values=self.values)


class TeamCollector(_Recording):
    collector_id = "t-team"
    namespace = "reddit"
    entity_kind = EntityKind.TEAM
    provides = ("excitement",)
    # One team only, on purpose: the away side of che-mun stays absent.
    values: ClassVar[dict] = {"che": {"excitement": 0.81}}


class LeagueCollector(_Recording):
    collector_id = "t-league"
    namespace = "pulse"
    entity_kind = EntityKind.LEAGUE
    provides = ("volatility",)
    values: ClassVar[dict] = {"seriea": {"volatility": 0.41}}


class MatchCollector(_Recording):
    collector_id = "t-match"
    namespace = "buzz"
    entity_kind = EntityKind.MATCH
    provides = ("mentions",)
    values: ClassVar[dict] = {"epl-2026-08-18-che-mun": {"mentions": 1284}}


class FailingCollector(_Recording):
    collector_id = "t-flaky"
    namespace = "flaky"
    entity_kind = EntityKind.MATCH
    provides = ("value",)
    values: ClassVar[dict] = {}

    def collect(self, slate: Slate) -> CollectionResult:
        self.calls += 1
        raise ConnectionResetError("connection reset by peer")


def _model(model_id: str, *features: str):
    class _M:
        pass

    _M.model_id = model_id
    _M.model_version = "0.1.0"
    _M.required_features = features
    _M.description = "test model"
    _M.score = lambda self, snapshot: ScoreResult(raw_score=1.0)
    return _M()


# --- resolution ------------------------------------------------------------


def test_one_collector_serves_many_models_with_a_single_fetch(slate):
    """The reason the tier exists. Three consumers, one fetch."""
    team = TeamCollector()
    registry = CollectorRegistry()
    registry.register(team)

    # Three models all wanting the same path.
    required = {"signals.reddit.home.excitement"}
    run_collectors(registry, slate, required, run_id="r", started_at="T")

    assert team.calls == 1


def test_a_collector_nothing_declares_is_never_invoked(slate):
    """Rate limits are real. Fetching data no model reads is waste that never
    surfaces as an error."""
    wanted, unwanted = MatchCollector(), TeamCollector()
    registry = CollectorRegistry()
    registry.register(wanted)
    registry.register(unwanted)

    run = run_collectors(
        registry, slate, {"signals.buzz.mentions"}, run_id="r", started_at="T"
    )

    assert wanted.calls == 1
    assert unwanted.calls == 0

    outcomes = {o.collector_id: o.outcome for o in run.outcomes}
    assert outcomes["t-team"] == "not_invoked", "and it must be recorded, not omitted"
    assert outcomes["t-match"] == "succeeded"


# --- registration ----------------------------------------------------------


def test_two_producers_claiming_one_path_is_rejected():
    """Otherwise the winner is whoever registered last, and a model silently reads
    a value from a collector it never intended."""
    registry = CollectorRegistry()
    registry.register(TeamCollector())

    class Clash(TeamCollector):
        collector_id = "t-team-2"

    with pytest.raises(CollectorRegistrationError, match="already provided by"):
        registry.register(Clash())


def test_duplicate_collector_id_is_rejected():
    registry = CollectorRegistry()
    registry.register(TeamCollector())
    with pytest.raises(CollectorRegistrationError, match="already registered"):
        registry.register(TeamCollector())


def test_a_model_declaring_a_signal_nothing_provides_fails_registration():
    """A typo here would otherwise skip every match forever, in silence."""
    collectors = CollectorRegistry()
    collectors.register(TeamCollector())

    models = Registry(provided_paths=collectors.provided_paths())
    with pytest.raises(RegistrationError, match="no registered collector"):
        models.register(_model("ghost", "signals.reddit.home.enthusiasm"))


def test_a_typo_in_a_canonical_path_still_names_the_schema():
    """Two different mistakes. Sending the author to the wrong one wastes a day."""
    models = Registry()
    with pytest.raises(RegistrationError, match="absent from"):
        models.register(_model("typo", "odds.total_lien"))


def test_a_team_keyed_collector_provides_both_sides():
    registry = CollectorRegistry()
    registry.register(TeamCollector())

    assert registry.provided_paths() == {
        "signals.reddit.home.excitement",
        "signals.reddit.away.excitement",
    }


# --- the joins -------------------------------------------------------------


def test_league_keyed_output_reaches_every_match_in_the_league(slate):
    registry = CollectorRegistry()
    registry.register(LeagueCollector())

    run = run_collectors(
        registry, slate, {"signals.pulse.volatility"}, run_id="r", started_at="T"
    )

    assert run.signals["seriea-2026-08-16-int-tor"]["pulse"] == {"volatility": 0.41}
    assert "epl-2026-08-15-ars-liv" not in run.signals, "other leagues untouched"


def test_a_team_keyed_value_for_one_side_leaves_the_other_absent(slate):
    """Partial coverage is routine here, so it must be representable rather than
    rounded off to 'present' or 'missing'."""
    registry = CollectorRegistry()
    registry.register(TeamCollector())

    run = run_collectors(
        registry, slate, {"signals.reddit.home.excitement"}, run_id="r", started_at="T"
    )
    reddit = run.signals["epl-2026-08-18-che-mun"]["reddit"]

    assert reddit["home"] == {"excitement": 0.81}
    assert "away" not in reddit


def test_a_model_needing_the_absent_side_skips_with_a_reason(slate):
    collectors = CollectorRegistry()
    collectors.register(TeamCollector())
    run = run_collectors(
        collectors, slate, {"signals.reddit.away.excitement"}, run_id="r", started_at="T"
    )

    models = Registry(provided_paths=collectors.provided_paths())
    models.register(_model("needs-away", "signals.reddit.away.excitement"))

    snapshots = [
        MatchSnapshot({**m.to_dict(), "signals": run.signals.get(m.match_id, {})})
        for m in slate.matches
    ]
    result = run_models(models, snapshots, computed_at="T", unavailable=run.unavailable_paths())

    skip = next(s for s in result.skips if s.match_id == "epl-2026-08-18-che-mun")
    assert skip.missing_features == ("signals.reddit.away.excitement",)
    assert not skip.caused_by_failure, "absent is not failed"
    assert skip.reason


# --- failure versus absence ------------------------------------------------


def test_one_collector_failing_does_not_abort_the_run(slate):
    flaky, ok = FailingCollector(), MatchCollector()
    registry = CollectorRegistry()
    registry.register(flaky)
    registry.register(ok)

    run = run_collectors(
        registry,
        slate,
        {"signals.flaky.value", "signals.buzz.mentions"},
        run_id="r",
        started_at="T",
    )

    outcomes = {o.collector_id: o.outcome for o in run.outcomes}
    assert outcomes["t-flaky"] == "failed"
    assert outcomes["t-match"] == "succeeded"
    assert run.signals["epl-2026-08-18-che-mun"]["buzz"] == {"mentions": 1284}


def test_a_raising_collector_is_a_failure_not_an_empty_result(slate):
    """An exception establishes nothing about whether data exists. Recording it as
    coverage would assert something the collector is not in a position to claim."""
    registry = CollectorRegistry()
    registry.register(FailingCollector())

    run = run_collectors(
        registry, slate, {"signals.flaky.value"}, run_id="r", started_at="T"
    )
    outcome = run.outcomes[0]

    assert outcome.outcome == "failed"
    assert "ConnectionResetError" in outcome.reason
    assert outcome.entities_without_data is None, "a failure has no coverage count"


def test_a_skip_caused_by_failure_is_distinguishable_from_absence(slate):
    """The property the whole run record exists for."""
    collectors = CollectorRegistry()
    collectors.register(FailingCollector())
    collectors.register(TeamCollector())

    run = run_collectors(
        collectors,
        slate,
        {"signals.flaky.value", "signals.reddit.away.excitement"},
        run_id="r",
        started_at="T",
    )

    models = Registry(provided_paths=collectors.provided_paths())
    models.register(_model("needs-flaky", "signals.flaky.value"))
    models.register(_model("needs-away", "signals.reddit.away.excitement"))

    snapshots = [
        MatchSnapshot({**m.to_dict(), "signals": run.signals.get(m.match_id, {})})
        for m in slate.matches
    ]
    result = run_models(models, snapshots, computed_at="T", unavailable=run.unavailable_paths())

    by_model = {s.model_id: s for s in result.skips}
    assert by_model["needs-flaky"].caused_by_failure
    assert "source unavailable" in by_model["needs-flaky"].reason
    assert not by_model["needs-away"].caused_by_failure


def test_a_successful_collector_reports_coverage_not_failure(slate):
    """'I looked and there is nothing' is a real answer, and it must be counted."""
    registry = CollectorRegistry()
    registry.register(TeamCollector())

    run = run_collectors(
        registry, slate, {"signals.reddit.home.excitement"}, run_id="r", started_at="T"
    )
    outcome = run.outcomes[0]

    assert outcome.outcome == "succeeded"
    assert outcome.entities_with_data == 1
    assert outcome.entities_without_data == len(slate.teams()) - 1
    assert outcome.reason is None


# --- order independence ----------------------------------------------------


def test_registration_order_does_not_change_the_assembled_signals(slate):
    """Collectors never read each other, so ordering must not matter -- the same
    property the model runner has, for the same reason."""
    required = {
        "signals.reddit.home.excitement",
        "signals.pulse.volatility",
        "signals.buzz.mentions",
    }

    forward = CollectorRegistry()
    for collector in (TeamCollector(), LeagueCollector(), MatchCollector()):
        forward.register(collector)

    backward = CollectorRegistry()
    for collector in (MatchCollector(), LeagueCollector(), TeamCollector()):
        backward.register(collector)

    a = run_collectors(forward, slate, required, run_id="r", started_at="T")
    b = run_collectors(backward, slate, required, run_id="r", started_at="T")

    assert a.signals == b.signals
    assert a.to_dict() == b.to_dict()


def test_the_run_record_conforms_to_the_contract(slate):
    from jsonschema import Draft202012Validator

    registry = CollectorRegistry()
    registry.register(TeamCollector())
    registry.register(FailingCollector())
    registry.register(MatchCollector())

    run = run_collectors(
        registry,
        slate,
        {"signals.reddit.home.excitement", "signals.flaky.value"},
        run_id="r",
        started_at="2026-08-14T04:00:00Z",
        completed_at="2026-08-14T04:00:11Z",
    )

    schema = json.loads((fixtures_dir().parent / "schemas" / "collection-run.json").read_text())
    Draft202012Validator(schema).validate(run.to_dict())
