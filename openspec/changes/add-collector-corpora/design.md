## Context

Collected signals exist only in memory, inside the `CollectionRun` that produced
them. `write_collection_run` records *that* a collector ran and what it covered;
`003_collection_run.sql:15-19` states plainly that the values themselves are not
stored, and names this change as where that closes.

The cost was theoretical while every collector read a fixture file off disk. It
became real with `recent-results`, which walks backwards through dated result
pages on goal.com until it has five completed matches per team — up to 120 dated
pages per run, against a source with no API, no contract, and no obligation to
serve anyone. Today, re-scoring after a one-line weight change pays that cost
again, because there is no way to score from data already fetched.

`refresh_after_seconds` has been on the `Collector` protocol since the tier was
introduced, carrying an explicit "DECLARED BUT NOT YET ENFORCED" and pointing
here (`collection.py:110-118`). `recent-results` declares 6 hours.

Two existing constraints shape everything below:

- **`collect(slate)` takes the whole slate.** There is no interface for asking a
  collector about a subset of entities. Adding one changes the contract for every
  collector.
- **`run_collectors` does not read the clock.** `run_id` and timestamps are
  injected, "for the same reason `run_models` injects `computed_at`: a run that
  reads the clock itself cannot be reproduced in a test" (`collectors.py:231`).

## Goals / Non-Goals

**Goals:**

- Persist collected signal values so a subsequent run can score without re-fetching.
- Make `refresh_after_seconds` mean something, decided by the collector's own
  declaration rather than by a global setting.
- Keep every distinct reason a collector did not run distinguishable in the run
  record. Adding reuse must not collapse "fresh enough" into "nothing needed it".
- Give the operator an explicit way to force collection.

**Non-Goals:**

- **Eviction and retention limits.** Rows accumulate. At a few hundred matches per
  window this is not a problem for a long time, and choosing a retention policy
  before an evaluation harness exists would be guessing at what history is worth.
- **Partial re-collection.** See D3.
- **Serving stale data when a collector fails.** See D6.
- **Un-hardcoding dates.** `STAMP`, `run_id="demo"`, `OFFLINE_AS_OF`, and the web
  page's `FROM`/`TO` are a separate change. This one interacts with `STAMP` in a
  way recorded under Risks, and does not fix it.
- **The unkeyed-corpus escape hatch.** `docs/STUBS.md` mentions "no collector
  consumes an unkeyed corpus" in the same row as the persistence gap. Only the
  persistence half is resolved here.

## Decisions

### D1. A new table, not an extension of `collection_run`

`collector_corpus` keyed by `(collector_id, entity_id, collected_at)`, carrying the
leaf values as JSON and the `run_id` that wrote them.

*Alternative rejected: add a values column to `collection_run_collector`.* That
table has one row per collector per run. Corpus values have a different lifetime —
they outlive the run that produced them, which is the entire point — and one run
can reuse a value another run wrote. Storing them there would make "which run
wrote this value" and "which runs used it" the same column, and the reuse count
would be unrecoverable.

*Alternative rejected: one JSON blob per run holding all signals.* Simple to write,
but freshness is a per-collector question, so every read would deserialise every
collector's output to answer it. It also makes a per-entity coverage check (D3)
into a full scan.

**Cost accepted:** a fourth concept in the store, and a migration.

### D2. The corpus is append-only, mirroring the score store

Rows are inserted, never updated. Reads resolve the latest row per
`(collector_id, entity_id)`.

This is consistency rather than novelty — `002_score_store.sql` already enforces
append-only by trigger for exactly this reason, and a corpus that is mutable while
scores are not would be a confusing exception. It also preserves the history an
evaluation harness would want to replay against, at no extra cost now.

**Cost accepted:** unbounded growth, with no eviction in this change. Recorded as
a non-goal rather than an oversight.

### D3. Reuse requires freshness AND full coverage of the asked-about entities

A collector is skipped as `reused` only when both hold:

1. its latest corpus is younger than `refresh_after_seconds`, measured against the
   run's injected `started_at`; and
2. the corpus has a row for **every** entity the slate asks about.

If either fails, the collector is invoked for the whole slate.

Condition 2 is the one that matters. Without it, a slate containing a team the
corpus has never seen would reuse, and that team would come back with no signals —
which every downstream tier would read as "the source has nothing for this team".
That is precisely the absence-versus-failure confusion the run record exists to
prevent, re-introduced one layer down. Missing coverage is not staleness, but it
must produce the same action.

*Alternative rejected: per-entity freshness with partial re-collection* — fetch
only the entities that are stale or missing. Genuinely better on network traffic,
and the natural thing to want for `recent-results`. Rejected because `collect(slate)`
has no way to express "these entities only". Adding one is a change to the
`Collector` protocol, which is Zone A and affects every collector ever written, and
it deserves its own argument rather than arriving as an implementation detail of
persistence.

**Cost accepted:** one unseen team on the slate re-fetches everything for that
collector. For `recent-results` on a fresh matchweek, that is the full walk. The
6-hour window still makes repeat runs within a working session free, which is the
case this change is for.

### D4. Freshness is measured against the injected `started_at`, not the clock

`run_collectors` keeps its promise not to read the clock. The stored `collected_at`
is the `started_at` of the run that wrote it, and the comparison is between two
injected values.

*Alternative rejected: call `datetime.now(UTC)` inside the freshness check.* It
would make the offline path behave "correctly" without waiting for the dates
change, at the price of making `run_collectors` unreproducible — the same inputs
would produce a different invocation decision depending on when the test ran. The
existing docstring commits against this, and buying a temporary convenience with
the property that makes the tier testable is a bad trade.

**Cost accepted:** while `pipeline.py` passes a frozen `STAMP`, every stored
corpus reads as zero seconds old and TTL expiry never fires on its own. See Risks.

### D5. `reused` is a fourth outcome, not a flavour of `not_invoked`

`collection_run_collector.outcome` gains `reused` alongside `succeeded`, `failed`,
and `not_invoked`, and the row records how many entities were served from the
corpus.

*Alternative rejected: record reuse as `not_invoked` with a reason string.* Both
mean "did not call the source", so the collapse is tempting. But they answer
opposite questions: `not_invoked` means no model wanted this data, `reused` means
a model did want it and got it. An operator reading the table to find out why a
match has no score needs to tell those apart, and a reason string is not something
you can index or count.

**Cost accepted:** a CHECK constraint change, and one more outcome every reader of
the run record must handle.

### D6. A failed collector does not fall back to its stored corpus

If collection fails, nothing is written, the failure is recorded as it is today,
and models depending on that collector skip the affected matches. The previous
corpus stays on disk, unused for this run.

*Alternative rejected: serve the last good corpus when the source is down.* This
is the most attractive rejected option in the change, and the one most likely to
be re-proposed. It would keep a demo working through an outage. It is deferred
because a score computed from yesterday's signals is a different claim from one
computed from today's, and nothing in a score row currently says which it was.
Making that visible needs snapshot persistence, which is `add-score-provenance`.
Shipping the fallback first would mean silently changing what a stored score means
in order to make a demo more convenient.

**Cost accepted:** during a source outage, a demo has no signals even though usable
data is sitting in the table.

### D7. `--refresh` forces collection

A flag on `scripts/pipeline.py` that bypasses the freshness check entirely and
invokes every needed collector. It does not delete anything; forced results are
appended like any other.

This is the operator's answer to "I know the source changed", and — until D4's
frozen-clock interaction is fixed by the dates change — the only way to force a
re-fetch at all.

## Risks / Trade-offs

**`STAMP` is frozen, so TTL expiry will not fire on its own until the follow-up
change lands.** → With `pipeline.py:58` passing a constant `started_at`, a corpus
written by one run reads as zero seconds old to the next, so after the first run
every collector reuses forever. On the fixture path this is harmless and arguably
correct: the offline demo is meant to be deterministic and should not re-walk
captured pages. On the live path it means automatic refresh does not work yet.
Mitigated by `--refresh` (D7), and resolved properly by the dates change, which
should follow immediately. **This ordering is worth stating in the PR**: the two
changes are independent to review but the second one is what makes the first one
behave as intended unattended.

**`run_id="demo"` is constant and `collection_run` uses `INSERT OR REPLACE`.** →
Every run overwrites the same run row today. Corpus rows carry `run_id` as
provenance, so they will all point at `"demo"` until the dates change gives runs
distinct ids. The corpus's own key does not include `run_id`, so nothing is lost
or overwritten — only the provenance pointer is less useful than it looks.

**Reuse makes a run look like it did more than it did.** → A run that reused every
corpus still writes scores and prints a full summary. Mitigated by the `reused`
outcome appearing in the pipeline's per-collector output, so the operator can see
that no network call happened.

**Coverage checking adds a query per collector per run.** → Negligible at this
size, and it is one indexed read against the latest rows rather than a scan.

**Re-running with a reused corpus produces identical snapshots.** → Not a problem:
`write_scores` is `INSERT OR IGNORE` on a key that already encodes "this model
version saw this exact input" (`scores.py:19-20`), so an identical re-run is a
no-op in the score store rather than a duplicate row.
