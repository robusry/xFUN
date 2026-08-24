"""The collector corpus in the database: what it stores, and what it refuses.

Two things here are worth a test rather than a reading. The corpus distinguishes
"never asked about this entity" from "asked, and the source had nothing", and those
are one JSON character apart in the table. And it is append-only by trigger rather
than by convention, which is only true if something has actually tried to break it.
"""

from __future__ import annotations

import sqlite3

import pytest
from xfun_store import (
    connect,
    corpus_freshness,
    migrate,
    read_corpus,
    write_corpus,
)

STAMP = "2026-08-14T04:00:00+00:00"
LATER = "2026-08-14T10:00:00+00:00"


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "corpus-test.db")
    list(migrate(c))
    yield c
    c.close()


def _write(conn, *, asked, values, collected_at=STAMP, run_id="r1"):
    write_corpus(
        conn,
        run_id=run_id,
        collector_id="t-team",
        entity_kind="team",
        asked=asked,
        values=values,
        collected_at=collected_at,
    )


def test_values_survive_the_run_that_produced_them(conn):
    _write(conn, asked=["che", "mun"], values={"che": {"excitement": 0.81}})

    read = read_corpus(conn, "t-team", ["che", "mun"])
    assert read.values["che"] == {"excitement": 0.81}
    assert read.covers_all


def test_asked_with_nothing_is_stored_distinctly_from_never_asked(conn):
    """The distinction the coverage check is built on."""
    _write(conn, asked=["che", "mun"], values={"che": {"excitement": 0.81}})

    read = read_corpus(conn, "t-team", ["che", "mun", "ars"])

    # mun was asked about and the source had nothing: a row, holding {}.
    assert read.values["mun"] == {}
    # ars was never asked about: no row at all.
    assert read.missing == frozenset({"ars"})
    assert not read.covers_all


def test_recollection_supersedes_without_erasing(conn):
    _write(conn, asked=["che"], values={"che": {"excitement": 0.81}})
    _write(conn, asked=["che"], values={"che": {"excitement": 0.42}}, collected_at=LATER)

    assert read_corpus(conn, "t-team", ["che"]).values["che"] == {"excitement": 0.42}

    rows = conn.execute(
        "SELECT collected_at FROM collector_corpus WHERE entity_id = 'che' "
        "ORDER BY collected_at"
    ).fetchall()
    assert [r["collected_at"] for r in rows] == [STAMP, LATER], "history was lost"


def test_freshness_is_the_latest_write_and_none_before_any(conn):
    assert corpus_freshness(conn, "t-team") is None

    _write(conn, asked=["che"], values={})
    assert corpus_freshness(conn, "t-team") == STAMP

    _write(conn, asked=["che"], values={}, collected_at=LATER)
    assert corpus_freshness(conn, "t-team") == LATER


def test_one_collector_does_not_see_another(conn):
    _write(conn, asked=["che"], values={"che": {"excitement": 0.81}})

    assert read_corpus(conn, "other-collector", ["che"]).missing == frozenset({"che"})
    assert corpus_freshness(conn, "other-collector") is None


def test_reading_no_entities_is_not_an_error(conn):
    read = read_corpus(conn, "t-team", [])
    assert read.values == {}
    assert read.covers_all, "an empty ask is vacuously covered"


def test_the_corpus_is_append_only(conn):
    """Enforced by trigger, not by callers politely not trying."""
    _write(conn, asked=["che"], values={"che": {"excitement": 0.81}})

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE collector_corpus SET values_json = '{}'")

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM collector_corpus")


def test_the_run_record_accepts_the_reused_outcome(conn):
    """005 rebuilds the CHECK constraint; a fresh database must carry the new one."""
    conn.execute(
        "INSERT INTO collection_run (run_id, slate_id, selection, started_at) "
        "VALUES ('r1', 's1', '{}', ?)",
        (STAMP,),
    )
    conn.execute(
        "INSERT INTO collection_run_collector "
        "(run_id, collector_id, entity_kind, outcome, provides) "
        "VALUES ('r1', 't-team', 'team', 'reused', '[]')"
    )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO collection_run_collector "
            "(run_id, collector_id, entity_kind, outcome, provides) "
            "VALUES ('r1', 't-other', 'team', 'invented', '[]')"
        )


def test_the_path_table_survives_the_rebuild(conn):
    """005 drops and recreates collection_run_collector, which collection_run_path
    references ON DELETE CASCADE. With foreign keys left on, the drop would have
    quietly taken the path rows with it."""
    referenced = conn.execute(
        "SELECT COUNT(*) AS n FROM pragma_foreign_key_list('collection_run_path') "
        "WHERE \"table\" = 'collection_run_collector'"
    ).fetchone()
    assert referenced["n"] > 0, "the path table lost its foreign key in the rebuild"
