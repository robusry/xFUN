"""The rights table, and which of the two answers wins.

The precedence is the interesting part and it is the reverse of what "prefer the
hand-verified data" would suggest. Per-match data from the source wins because it can
express a split that no league-wide line can; the table answers only where the source
is silent, which is where rights are constant.

The failure mode this guards against is a confidently wrong provider. Every other
part of the system treats `unknown` as a first-class answer, and this is where that
principle either holds or quietly stops holding.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from xfun_ingestion.schedule import (
    RightsTableError,
    default_rights_path,
    load_rights,
    resolve_providers,
)

MLS = "usa-major-league-soccer"
MLS_NEXT_PRO = "usa-mls-next-pro"
LIGA_MX = "mexico-liga-mx"
EPL = "england-premier-league"


@pytest.fixture
def rights():
    return load_rights()


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "rights.yaml"
    path.write_text(body)
    return path


# --- the shipped table ---------------------------------------------------


def test_the_shipped_table_loads() -> None:
    assert load_rights(default_rights_path())


def test_every_entry_records_when_and_against_what(rights) -> None:
    for entry in rights.values():
        assert isinstance(entry.verified_on, date)
        assert entry.source.startswith("http")


def test_mls_is_league_wide(rights) -> None:
    assert rights[MLS].providers == ("Apple TV",)


def test_mls_next_pro_is_not_apple_tv(rights) -> None:
    """Worth asserting because it is the plausible wrong answer. Apple holds
    streaming rights through 2032, but the 2026 broadcast arrangement is
    OneFootball, and every aggregator surveyed listed no provider at all."""
    providers = rights[MLS_NEXT_PRO].providers

    assert "OneFootball" in providers
    assert "Apple TV" not in providers


def test_split_rights_leagues_are_absent(rights) -> None:
    """Liga MX rights are held per club and the Premier League splits a matchweek
    between broadcasters. A league-wide line for either would be wrong for real
    matches every week, so neither belongs in this file."""
    assert LIGA_MX not in rights
    assert EPL not in rights


# --- what the loader refuses ---------------------------------------------


def test_missing_verified_on_fails_the_load(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "leagues:\n"
        "  usa-example:\n"
        "    providers: [Some Network]\n"
        "    source: https://example.test/announcement\n",
    )

    with pytest.raises(RightsTableError, match="verified_on"):
        load_rights(path)


def test_missing_source_fails_the_load(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "leagues:\n"
        "  usa-example:\n"
        "    providers: [Some Network]\n"
        "    verified_on: 2026-08-03\n",
    )

    with pytest.raises(RightsTableError, match="source"):
        load_rights(path)


def test_a_bad_entry_rejects_the_whole_file(tmp_path: Path) -> None:
    """Skipping the bad entry would turn a typo into a league whose matches quietly
    stop reaching the slate, which looks exactly like a quiet week."""
    path = _write(
        tmp_path,
        "leagues:\n"
        "  usa-good:\n"
        "    providers: [Good Network]\n"
        "    verified_on: 2026-08-03\n"
        "    source: https://example.test/a\n"
        "  usa-bad:\n"
        "    providers: [Bad Network]\n"
        "    source: https://example.test/b\n",
    )

    with pytest.raises(RightsTableError):
        load_rights(path)


def test_a_quoted_date_is_not_a_date(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "leagues:\n"
        "  usa-example:\n"
        "    providers: [Some Network]\n"
        "    verified_on: 'sometime last year'\n"
        "    source: https://example.test/a\n",
    )

    with pytest.raises(RightsTableError, match="must be a date"):
        load_rights(path)


def test_an_empty_provider_list_fails(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "leagues:\n"
        "  usa-example:\n"
        "    providers: []\n"
        "    verified_on: 2026-08-03\n"
        "    source: https://example.test/a\n",
    )

    with pytest.raises(RightsTableError):
        load_rights(path)


def test_a_missing_file_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(RightsTableError, match="no rights table"):
        load_rights(tmp_path / "absent.yaml")


# --- resolution ----------------------------------------------------------


def test_source_providers_win_over_the_table(rights) -> None:
    """The split-rights case. A Premier League match is on Peacock this week and
    USA Network next, and only the source can say which."""
    availability = resolve_providers(("Peacock", "NBC"), MLS, rights)

    assert availability.known
    assert availability.providers == ("Peacock", "NBC")
    assert availability.resolved_from == "source"


def test_the_table_answers_when_the_source_is_silent(rights) -> None:
    availability = resolve_providers((), MLS_NEXT_PRO, rights)

    assert availability.known
    assert "OneFootball" in availability.providers
    assert availability.resolved_from == "rights-table"


def test_neither_answering_is_unknown(rights) -> None:
    availability = resolve_providers((), LIGA_MX, rights)

    assert not availability.known
    assert availability.status == "unknown"
    assert availability.providers == ()
    assert availability.resolved_from is None


def test_unknown_is_reached_rather_than_guessed(rights) -> None:
    """The system must not substitute a plausible provider for an absent one."""
    availability = resolve_providers((), "some-league-nobody-verified", rights)

    assert availability.status == "unknown"
    assert availability.providers == ()


def test_resolution_works_with_no_table_at_all() -> None:
    assert resolve_providers(("ESPN+",), MLS, None).known
    assert not resolve_providers((), MLS, None).known
