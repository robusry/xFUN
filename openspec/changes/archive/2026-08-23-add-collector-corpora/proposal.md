## Why

Nothing persists collected signals between runs, so every run re-collects from
scratch. That was free when collectors read fixture files. It stopped being free
when `recent-results` started walking backwards through up to 120 dated pages of
an unofficial source on every invocation, and it is the reason
`refresh_after_seconds` has been declared-but-unenforced since the collector tier
was introduced (`packages/scoring-contract/src/xfun_contract/collection.py:110`,
which already names this change as where enforcement arrives).

The practical consequence is that there is no such thing as refreshing the data
as a separate act. Re-scoring requires re-fetching, so a demo, a weight change,
and a genuine data update all cost the same network traffic against a source that
publishes no API and owes this project nothing.

## What Changes

- **Collected signals are persisted**, keyed by run, collector, and entity id, so
  a later run can read them back instead of re-fetching.
- **`refresh_after_seconds` becomes enforced.** A collector whose stored corpus is
  younger than its declared window is not invoked; its persisted values are reused
  and the run records that it was reused rather than run.
- **A new `not_invoked` sibling outcome, `reused`**, so the run record continues to
  distinguish every reason a collector did not run. "Nothing declared anything it
  provides", "its data was still fresh", and "it ran and found nothing" stay three
  different answers.
- **Failure never overwrites a good corpus.** A failed collector leaves the last
  successful corpus in place and records the failure; it does not persist an empty
  result over data that was fine.
- **A `--refresh` flag forces collection** regardless of stored freshness, for when
  the operator knows the source has changed.
- Refresh and scoring remain **one command**. Persistence makes them separable;
  this change does not separate them.

Not in scope, deliberately: the hardcoded `STAMP`, `run_id="demo"`,
`OFFLINE_AS_OF`, and the web page's `FROM`/`TO` constants. Those are a follow-up
change. This one is about what gets stored, not about what "now" means.

## Capabilities

### New Capabilities

- `collector-corpora`: persistence of collected signal values between runs —
  what is stored, how freshness is decided from the collector's own declaration,
  how a reused corpus is recorded, and what happens to a stored corpus when a
  later collection fails.

### Modified Capabilities

- `data-collection`: the requirement "A collector runs once per slate, and only
  when a model needs it" gains a second condition. Being needed by an active model
  is no longer sufficient to invoke a collector; its stored corpus must also be
  stale. The run record gains a `reused` outcome alongside `succeeded`, `failed`,
  and `not_invoked`.

- `schedule-acquisition`: "Broadcast providers resolve from per-match data before
  league-level rights" states explicitly that absence from the rights table does
  not by itself keep a competition off the slate, and gains a scenario for a
  split-rights competition the table deliberately omits.

  This is unrelated to persistence and is folded in because the live verification
  run for this change is what surfaced it. The existing requirement was already
  correct — its first scenario resolves per-match data ahead of the table
  "because league-level rights cannot express a split-rights competition" — but it
  stated the slate consequence only on the negative path. The positive path left
  it to be inferred, and the project documentation had inferred it the other way,
  asserting as settled fact that Liga MX could never reach the slate. On
  2026-08-23 it did, with per-match providers from the schedule source and no
  rights-table entry, which is the outcome `us-broadcast-rights.yaml:63` predicted
  would follow if "the source starts answering for it". Closing the asymmetry
  makes the spec say what the code already did.

## Impact

**Zone A** — `packages/scoring-runtime/collectors.py` decides invocation and
builds the run record, and `packages/scoring-contract/` documents
`refresh_after_seconds` as unenforced. Both are shared machinery every collector
and model depends on, so specs are required.

**Zone B** — `packages/store/` gains corpus read and write; `scripts/pipeline.py`
gains the `--refresh` flag.

**Zone C** — `infra/migrations/005_collector_corpus.sql` is new.

Affected code:

- `infra/migrations/` — one new migration, and the "NOT stored here" comment in
  `003_collection_run.sql:15` becomes wrong and must be corrected rather than left
  to mislead.
- `packages/store/src/xfun_store/collection.py` — corpus write and freshness read.
- `packages/scoring-runtime/src/xfun_runtime/collectors.py` — `run_collectors`
  consults stored freshness before invoking, and emits the `reused` outcome.
- `packages/scoring-contract/src/xfun_contract/collection.py` — the
  `refresh_after_seconds` docstring stops saying "DECLARED BUT NOT YET ENFORCED".
- `scripts/pipeline.py` — `--refresh`.
- `docs/STUBS.md` — resolves the "Also missing" row under **Collectors**
  ("Nothing persists collected signals between runs, so `refresh_after_seconds`
  is declared but not enforced, and a re-score requires a re-collect"). The
  unkeyed-corpus escape hatch named in the same row is **not** resolved here and
  keeps its entry.

No API or contract change: the corpus is internal, and no response shape moves.
