# store

**Real, not placeholder** — though the database engine is (SQLite, see below).

Persistence for canonical entities and the append-only score store. Used by
ingestion, the scoring runner, and the API; belongs to none of them, which is why
it is its own package.

## Append-only is enforced by the database

`model_score` has `BEFORE UPDATE` and `BEFORE DELETE` triggers that abort. There
is no `update_score` function here and there never will be — a rule the database
refuses to break is worth more than one the application politely observes.

Re-scoring inserts a new row with a new `snapshot_hash`. The superseded row stays
queryable, which is what makes "did the new model change last weekend's ranking?"
answerable by query rather than by memory.

Retiring a model means removing it from scoring runs and recipes — never deleting
its history.

## Snapshot round-trip

`load_snapshots()` rebuilds `MatchSnapshot`s from canonical entities, and the
result must validate against `contracts/schemas/match-snapshot.json`. Optional
blocks are omitted rather than emitted as nulls, so a match with no odds produces
a snapshot with no `odds` key and models requiring odds skip it.

⚠️ SQLite, at `.data/xfun.db`. Chosen so the demo runs with no daemon. Expected to
become Postgres; the dialect differences are real. See
[docs/STUBS.md](../../docs/STUBS.md).
