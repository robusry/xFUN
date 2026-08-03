-- Where a US viewer can watch a match.
--
-- Deliberately NOT part of the match snapshot. A snapshot is what a model sees,
-- and a model must not score a match differently according to who broadcasts it
-- -- that would make entertainment value a function of distribution. So this
-- lives beside the match rather than in it, and `match-snapshot.json` stays
-- closed against it. See design D6 of add-live-schedule.
--
-- `status` is a real value and not a nullability workaround. "unknown" is a
-- first-class answer everywhere in this system, because a confidently wrong
-- provider is the failure a viewer notices immediately -- being told a match is
-- on a service that does not carry it. A match with no row here and a match with
-- a row saying "unknown" mean the same thing to a reader, and both are honest;
-- what neither may become is a guess.
--
-- `resolved_from` records WHICH of the two resolution steps answered:
--
--   source        the schedule source named providers for this specific match
--   rights-table  the source was silent, and a hand-verified league-wide entry
--                 answered instead
--
-- That distinction ages differently and is worth keeping. A hand-maintained
-- answer was true on the day someone checked, and US rights move between
-- seasons; a per-match answer came from the source on the day it ran. When one
-- of them turns out to be wrong, this column is what says which to go and fix.

CREATE TABLE IF NOT EXISTS match_availability (
    match_id      TEXT PRIMARY KEY REFERENCES match(match_id),
    status        TEXT NOT NULL CHECK (status IN ('known', 'unknown')),
    resolved_from TEXT CHECK (resolved_from IN ('source', 'rights-table')),
    resolved_at   TEXT NOT NULL,

    -- A known status must name someone; an unknown one must not. Without this a
    -- row can claim to know and list nobody, which reads as "we checked and it
    -- is on nothing" -- a different and wrong claim.
    CHECK (
        (status = 'unknown' AND resolved_from IS NULL)
        OR (status = 'known' AND resolved_from IS NOT NULL)
    )
);

-- Providers are a set per match, not a delimited string, so that a split-rights
-- match reads as what it is: several carriers, each nameable. `position` keeps
-- the source's ordering, which is the order a reader would expect to see them.
CREATE TABLE IF NOT EXISTS match_provider (
    match_id TEXT NOT NULL REFERENCES match_availability(match_id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    name     TEXT NOT NULL,
    PRIMARY KEY (match_id, position)
);

CREATE INDEX IF NOT EXISTS idx_match_provider_match ON match_provider(match_id);

-- What happened when the schedule was acquired.
--
-- Same reasoning as collection_run, one tier earlier. Two very different
-- situations leave an identical empty slate:
--
--   the source answered and nothing in the window is watchable   (coverage)
--   the source could not be reached, or changed shape            (failure)
--
-- The first is correct and common -- the leagues in scope go between seasons,
-- and a quiet week is a real answer. The second establishes nothing. Without
-- this table a source that broke looks exactly like a fortnight with no
-- football, and the pipeline downstream of it reports, correctly and uselessly,
-- that there was nothing to score.
--
-- `matches_seen` is counted BEFORE the watchable filter and `matches_watchable`
-- after, so a run where the source answered fully but named no providers is
-- distinguishable from one where it returned nothing at all. Those two also
-- produce the same empty slate.
CREATE TABLE IF NOT EXISTS schedule_run (
    run_id            TEXT NOT NULL PRIMARY KEY,
    source_id         TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('ok', 'failed')),
    reason            TEXT,
    window_start_utc  TEXT NOT NULL,
    window_end_utc    TEXT NOT NULL,
    matches_seen      INTEGER NOT NULL DEFAULT 0,
    matches_watchable INTEGER NOT NULL DEFAULT 0,
    ran_at            TEXT NOT NULL,

    -- A failure must say why. "It broke" without a reason is the thing this
    -- table exists to prevent, and an ok run has nothing to explain.
    CHECK (
        (status = 'failed' AND reason IS NOT NULL)
        OR (status = 'ok' AND reason IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_schedule_run_ran_at ON schedule_run(ran_at);
