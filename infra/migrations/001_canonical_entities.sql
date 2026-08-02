-- Canonical entities: what ingestion writes, and what snapshots are assembled from.
--
-- SQLite for the skeleton. Replaced by Postgres when real ingestion lands; the
-- dialect differences here are small but real (see docs/STUBS.md).

CREATE TABLE IF NOT EXISTS league (
    id      TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    country TEXT
);

CREATE TABLE IF NOT EXISTS team (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match (
    match_id     TEXT PRIMARY KEY,
    league_id    TEXT NOT NULL REFERENCES league(id),
    kickoff_utc  TEXT NOT NULL,
    home_team_id TEXT NOT NULL REFERENCES team(id),
    away_team_id TEXT NOT NULL REFERENCES team(id)
);

CREATE INDEX IF NOT EXISTS idx_match_kickoff ON match(kickoff_utc);

-- Odds are optional and time-varying. A match with no row here is routine, not an
-- error: it is a match with no market coverage, and models requiring odds skip it.
CREATE TABLE IF NOT EXISTS odds_snapshot (
    match_id     TEXT NOT NULL REFERENCES match(match_id),
    captured_at  TEXT NOT NULL,
    total_line   REAL,
    over_price   REAL,
    under_price  REAL,
    home_price   REAL,
    draw_price   REAL,
    away_price   REAL,
    PRIMARY KEY (match_id, captured_at)
);

CREATE TABLE IF NOT EXISTS team_form (
    match_id          TEXT NOT NULL REFERENCES match(match_id),
    side              TEXT NOT NULL CHECK (side IN ('home', 'away')),
    matches           INTEGER NOT NULL,
    goals_for_avg     REAL,
    goals_against_avg REAL,
    PRIMARY KEY (match_id, side)
);

CREATE TABLE IF NOT EXISTS table_position (
    match_id      TEXT PRIMARY KEY REFERENCES match(match_id),
    home_position INTEGER,
    away_position INTEGER,
    total_teams   INTEGER,
    matchweek     INTEGER
);
