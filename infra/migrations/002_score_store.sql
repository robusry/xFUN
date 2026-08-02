-- The score store.
--
-- Raw model scores are the system's ONLY score truth. Calibrated and composed
-- scores are derived at read time -- because the calibration cohort is chosen by
-- the caller per request, a calibrated value is not a property of a row.
--
-- Append-only is enforced here, by trigger, rather than in application code. A
-- rule the database refuses to break is worth more than one the application
-- politely observes.

CREATE TABLE IF NOT EXISTS model_score (
    match_id      TEXT    NOT NULL,
    model_id      TEXT    NOT NULL,
    model_version TEXT    NOT NULL,
    snapshot_hash TEXT    NOT NULL,
    raw_score     REAL    NOT NULL,
    components    TEXT    NOT NULL,  -- JSON object
    computed_at   TEXT    NOT NULL,
    PRIMARY KEY (match_id, model_id, model_version, snapshot_hash)
);

CREATE INDEX IF NOT EXISTS idx_model_score_match ON model_score(match_id);
CREATE INDEX IF NOT EXISTS idx_model_score_model ON model_score(model_id, model_version);
CREATE INDEX IF NOT EXISTS idx_model_score_computed ON model_score(computed_at);

-- Re-scoring inserts a new row with a new snapshot_hash. The superseded row stays
-- queryable forever: that is what makes "did the new model change last weekend's
-- ranking?" answerable by query rather than by memory.
CREATE TRIGGER IF NOT EXISTS model_score_no_update
BEFORE UPDATE ON model_score
BEGIN
    SELECT RAISE(ABORT,
        'model_score is append-only: scores are never updated. Insert a new row.');
END;

-- Retiring a model means removing it from scoring runs and recipes, not deleting
-- its history. (RAISE takes a literal only, so the message is kept short.)
CREATE TRIGGER IF NOT EXISTS model_score_no_delete
BEFORE DELETE ON model_score
BEGIN
    SELECT RAISE(ABORT, 'model_score is append-only: scores are never deleted.');
END;

-- Model registry metadata. Retirement lives here, so a retired model stops
-- producing new rows while every row it ever produced remains readable.
CREATE TABLE IF NOT EXISTS model_registry (
    model_id      TEXT PRIMARY KEY,
    model_version TEXT NOT NULL,
    description   TEXT,
    retired       INTEGER NOT NULL DEFAULT 0,
    features      TEXT NOT NULL  -- JSON array of dotted feature paths
);

-- Serving reads take the most recent row per (match, model); evaluation reads can
-- still reach every superseded row in the base table.
CREATE VIEW IF NOT EXISTS latest_model_score AS
SELECT s.*
FROM model_score s
JOIN (
    SELECT match_id, model_id, MAX(computed_at) AS computed_at
    FROM model_score
    GROUP BY match_id, model_id
) newest
  ON  s.match_id    = newest.match_id
  AND s.model_id    = newest.model_id
  AND s.computed_at = newest.computed_at;
