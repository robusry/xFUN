-- The collector corpus: collected signal VALUES, persisted between runs.
--
-- 003_collection_run.sql records that a collector ran and what it covered. It
-- deliberately did not store what the collector returned, which meant re-scoring
-- required re-collecting. That was free when every collector read a fixture file
-- off disk. It stopped being free when `recent-results` began walking backwards
-- through up to 120 dated pages of a source with no API and no obligation to
-- serve anyone.
--
-- Storing the values here is what lets a run decide NOT to call a source, which
-- is what makes `refresh_after_seconds` mean something.
--
-- Why a separate table rather than a column on collection_run_collector: a corpus
-- row outlives the run that produced it -- that is the entire point -- and one run
-- may reuse a value a different run wrote. Putting values on the per-run row would
-- make "which run wrote this" and "which runs used it" the same column, and the
-- reuse would be unrecoverable.

CREATE TABLE IF NOT EXISTS collector_corpus (
    collector_id TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    entity_kind  TEXT NOT NULL,  -- match | team | league; how it joins onto matches
    values_json  TEXT NOT NULL,  -- JSON object: leaf name -> value
    collected_at TEXT NOT NULL,  -- the writing run's started_at, NOT the wall clock
    run_id       TEXT NOT NULL,  -- provenance only; not part of the key
    PRIMARY KEY (collector_id, entity_id, collected_at),
    CHECK (entity_kind IN ('match', 'team', 'league'))
);

-- The read is always "latest per collector and entity", and the coverage check is
-- "which of these entity ids do I have at all". Both are served by this order.
CREATE INDEX IF NOT EXISTS idx_corpus_lookup
    ON collector_corpus(collector_id, entity_id, collected_at DESC);

-- Append-only, for the same reason the score store is: a corpus that could be
-- mutated while scores cannot would be a confusing exception to the one rule this
-- database enforces everywhere else. It also preserves the history an evaluation
-- harness would want to replay against, at no cost today.
--
-- Note there is no eviction anywhere in this schema. Rows accumulate. At a few
-- hundred matches per window that is fine for a long time, and choosing a
-- retention policy before an evaluation harness exists would be guessing at what
-- history is worth keeping.
CREATE TRIGGER IF NOT EXISTS collector_corpus_no_update
BEFORE UPDATE ON collector_corpus
BEGIN
    SELECT RAISE(ABORT,
        'collector_corpus is append-only: collect again to supersede.');
END;

CREATE TRIGGER IF NOT EXISTS collector_corpus_no_delete
BEFORE DELETE ON collector_corpus
BEGIN
    SELECT RAISE(ABORT, 'collector_corpus is append-only: rows are never deleted.');
END;

-- Serving reads take the most recent row per (collector, entity); a later
-- evaluation read can still reach every superseded row in the base table.
CREATE VIEW IF NOT EXISTS latest_collector_corpus AS
SELECT c.*
FROM collector_corpus c
JOIN (
    SELECT collector_id, entity_id, MAX(collected_at) AS collected_at
    FROM collector_corpus
    GROUP BY collector_id, entity_id
) newest
  ON  c.collector_id = newest.collector_id
  AND c.entity_id    = newest.entity_id
  AND c.collected_at = newest.collected_at;


-- ---------------------------------------------------------------------------
-- Add `reused` to the collection_run_collector outcome enum.
--
-- A collector that was not invoked because its corpus was still good is NOT the
-- same as one that was not invoked because nothing declared anything it provides.
-- Both mean "did not call the source" and they answer opposite questions: the
-- first means a model wanted the data and got it, the second means no model
-- wanted it. An operator reading this table to find out why a match went unscored
-- has to be able to tell them apart, and by something countable rather than a
-- reason string.
--
-- SQLite cannot alter a CHECK constraint, so this is the documented table
-- rebuild. Foreign keys are disabled around it because collection_run_path
-- references this table ON DELETE CASCADE -- with them on, the DROP below would
-- cascade and silently take the path rows with it.
-- ---------------------------------------------------------------------------

PRAGMA foreign_keys = OFF;

CREATE TABLE collection_run_collector_new (
    run_id                TEXT    NOT NULL,
    collector_id          TEXT    NOT NULL,
    entity_kind           TEXT    NOT NULL,  -- match | team | league
    outcome               TEXT    NOT NULL,  -- succeeded | failed | not_invoked | reused
    reason                TEXT,              -- why, when outcome = failed
    entities_with_data    INTEGER,           -- when succeeded; when reused, served from corpus
    entities_without_data INTEGER,           -- coverage, not failure
    provides              TEXT    NOT NULL,  -- JSON array of claimed paths
    PRIMARY KEY (run_id, collector_id),
    FOREIGN KEY (run_id) REFERENCES collection_run(run_id) ON DELETE CASCADE,
    CHECK (outcome IN ('succeeded', 'failed', 'not_invoked', 'reused')),
    CHECK (entity_kind IN ('match', 'team', 'league'))
);

INSERT INTO collection_run_collector_new
SELECT run_id, collector_id, entity_kind, outcome, reason,
       entities_with_data, entities_without_data, provides
FROM collection_run_collector;

DROP TABLE collection_run_collector;

ALTER TABLE collection_run_collector_new RENAME TO collection_run_collector;

CREATE INDEX IF NOT EXISTS idx_run_collector_outcome
    ON collection_run_collector(outcome);

PRAGMA foreign_keys = ON;
