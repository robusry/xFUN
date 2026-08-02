-- The collection run record.
--
-- This exists to answer one question that is otherwise unanswerable: why does
-- this match carry no score from this model? Two very different situations
-- produce an identical hole in the snapshot --
--
--   the source was consulted and had nothing for this match   (coverage)
--   the source could not be reached at all                    (failure)
--
-- The first is a permanent, correct answer. The second establishes nothing and
-- the match may well be scoreable on the next run. Without this table they are
-- indistinguishable, and a source that was down for a week looks exactly like a
-- source with nothing to say.
--
-- NOT stored here: the collected signal values themselves. Signals are folded
-- into a snapshot at assembly time, and snapshots are not persisted either --
-- see docs/STUBS.md and `add-score-provenance`. Re-scoring therefore requires
-- re-collecting. That gap is inherited from snapshots rather than introduced
-- here, and closing it is `add-collector-corpora`.

CREATE TABLE IF NOT EXISTS collection_run (
    run_id       TEXT NOT NULL PRIMARY KEY,
    slate_id     TEXT NOT NULL,  -- content hash of the match set; see slate.json
    selection    TEXT NOT NULL,  -- JSON: the rule that chose the matches
    started_at   TEXT NOT NULL,
    completed_at TEXT            -- NULL while the run is in flight
);

CREATE INDEX IF NOT EXISTS idx_collection_run_slate ON collection_run(slate_id);
CREATE INDEX IF NOT EXISTS idx_collection_run_started ON collection_run(started_at);

-- One row per collector CONSIDERED for the run, including those not invoked.
-- Recording a collector that was correctly skipped is not noise: "nothing
-- declared anything it provides" is a different answer from "it ran and found
-- nothing", and an operator reading this table needs to tell them apart.
CREATE TABLE IF NOT EXISTS collection_run_collector (
    run_id                TEXT    NOT NULL,
    collector_id          TEXT    NOT NULL,
    entity_kind           TEXT    NOT NULL,  -- match | team | league
    outcome               TEXT    NOT NULL,  -- succeeded | failed | not_invoked
    reason                TEXT,              -- why, when outcome = failed
    entities_with_data    INTEGER,           -- meaningful only when succeeded
    entities_without_data INTEGER,           -- coverage, not failure
    provides              TEXT    NOT NULL,  -- JSON array of claimed paths
    PRIMARY KEY (run_id, collector_id),
    FOREIGN KEY (run_id) REFERENCES collection_run(run_id) ON DELETE CASCADE,
    CHECK (outcome IN ('succeeded', 'failed', 'not_invoked')),
    CHECK (entity_kind IN ('match', 'team', 'league'))
);

CREATE INDEX IF NOT EXISTS idx_run_collector_outcome
    ON collection_run_collector(outcome);

-- The paths a run claimed, flattened so that "which collector should have
-- provided this feature, and what happened to it?" is one query rather than a
-- JSON scan. Provenance lives here rather than in the path itself, which is what
-- lets a signal change producer without every model that declares it breaking.
CREATE TABLE IF NOT EXISTS collection_run_path (
    run_id       TEXT NOT NULL,
    path         TEXT NOT NULL,
    collector_id TEXT NOT NULL,
    PRIMARY KEY (run_id, path),
    FOREIGN KEY (run_id, collector_id)
        REFERENCES collection_run_collector(run_id, collector_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_run_path_path ON collection_run_path(path);
