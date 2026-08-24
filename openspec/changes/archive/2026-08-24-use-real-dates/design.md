## Context

Two constants in `scripts/pipeline.py` stand in for the clock:

```python
STAMP = "2026-08-14T04:00:00+00:00"
OFFLINE_AS_OF = date(2026, 8, 14)
```

`STAMP` is passed as `computed_at` on every score and as `started_at`/`completed_at`
on every collection run, **on both paths**. `OFFLINE_AS_OF` is different in kind: it
tells `recent-results` what "now" means when scanning captured pages, and it is
load-bearing for reproducibility rather than a placeholder. Its own docstring says
so — the golden captures were taken walking back from that date, and a scan starting
anywhere else runs off the end of them.

A third constant lives in `packages/web/src/App.tsx:23`, whose comment already
concedes the point: "Real date handling arrives with real ingestion."

The constraint that shapes the whole design: `run_collectors` and `run_models` take
injected timestamps and must keep doing so. Their docstrings commit to it, and
`add-collector-corpora` built the corpus freshness rule on top of that promise. The
fix is to inject a *real* value on the live path, not to let those functions read a
clock.

## Goals / Non-Goals

**Goals:**

- A live run's stored data carries the time it actually ran.
- The offline path stays byte-for-byte reproducible, on the same code.
- Make `add-collector-corpora`'s freshness rule fire without `--refresh`.
- Remove the hardcoded window from the web page without breaking the offline demo.

**Non-Goals:**

- **Separating fixture data from live data in the store.** Eight fixture matches
  now sit alongside two hundred live ones. Left alone: it needs a decision about
  whether the two paths share a store, which is larger than timestamps.
- **Routing, a date picker, or filtering on the web page.** `docs/STUBS.md` lists
  four things missing there; this resolves one.
- **Moving `OFFLINE_AS_OF`.** It is not a placeholder. See D2.
- **Corpus retention.** Still unbounded, still deliberate.

## Decisions

### D1. One clock read, at the top, injected downward

`main()` resolves the run's instant once and threads it through everything that
needs a timestamp. No function below `main` reads the clock.

*Alternative rejected: let `run_collectors` and `run_models` default to
`datetime.now(UTC)` when no stamp is passed.* They already have exactly that
fallback, so this is nearly free — and it is wrong. A run that reads the clock
mid-pipeline can produce a `computed_at` earlier than the `collected_at` of the
signals it scored, and the corpus freshness check would compare two independently
sampled clocks. Sampling once and passing it down makes the whole run consistent
with itself by construction.

**Cost accepted:** one more parameter threaded through `main`.

### D2. The fixture path keeps a fixed anchor; only the live path uses the clock

`--live` takes its stamp from the clock. The default path keeps a constant.

This is the decision most likely to read as a half-measure, so: making the fixture
path clock-driven would break `recent-results` immediately. It scans backwards from
"now" through captured pages that exist only for a fixed range of dates, so a scan
anchored to today walks off the end of the corpus and returns nothing. It would also
end determinism — CI compares against golden output, and two runs on different days
would differ.

The offline path is a *reproduction*, not a simulation of today. That is what makes
it useful for testing.

*Alternative rejected: derive the fixture stamp from the newest captured page.* More
self-maintaining, and it hides the anchor inside a directory listing where nobody
looking for it would find it. An explicit constant with a docstring explaining why
it is frozen is more honest than an implicit one.

**Cost accepted:** two paths with different notions of "now", which must be
explained wherever either appears.

### D3. Run identifiers derive from the run's timestamp

`run-<iso8601>` on the live path, replacing `run_id="demo"`. `run_collectors`
already builds exactly this when no id is passed, so the change is to stop passing
one. The fixture path keeps a constant id, so repeat offline runs remain idempotent
rather than accumulating identical records.

*Alternative rejected: a UUID per run.* Unique, and unsortable and unreadable. A
timestamp-derived id sorts chronologically in the table and tells an operator when
the run happened without a join.

**Cost accepted:** two runs within the same second collide. At one run per demo
this is not a real risk, and the collision is an `INSERT OR REPLACE` rather than a
crash.

### D4. Omitted `from`/`to` means "whatever the store holds", and the response says so

Both parameters become optional. When either is omitted, the API does not
substitute a window — it queries without that bound. `load_snapshots` already
accepts `None` for both and omits the clause, so this is a parameter change rather
than new query logic.

The response gains a `window` object stating the range actually served. This is not
decoration. The project already requires every score response to state its cohort
and alias, on the reasoning that a number whose basis the caller did not choose is
uninterpretable without being told the basis. A defaulted window is the same
situation: a caller who sent no dates cannot otherwise tell whether it got
everything, or a truncated page, or nothing because the store is empty.

*Alternative rejected: default to `today` through `today + 10 days`*, matching the
`us-watchable` slate rule. Tempting because it mirrors the rule that put the matches
there. Rejected because it would make the offline demo render empty — the fixture
matches sit in the past — and the fresh-clone-with-no-network path is something this
project treats as load-bearing. A default that works on one path and silently
blanks the other is worse than no default.

*Alternative rejected: keep them required and have the web compute a window.* Zone
C only, no contract change, no specs. It has the same empty-offline-demo problem,
and it puts a policy decision in the least authoritative tier.

**Cost accepted:** an unbounded default response grows with the store. Today that is
roughly two hundred matches. There is no pagination, and this change does not add
any — but it moves that from "theoretical" to "worth watching", which is recorded
under Risks rather than fixed here.

### D5. The web page asks for nothing

`FROM` and `TO` are deleted rather than replaced with computed values. The page
requests the match list with no date arguments and renders the window the response
reports.

Putting the window policy in the API rather than the page means the mobile client,
`curl`, and the generated TypeScript client all get the same default without each
reimplementing it.

**Cost accepted:** the page can no longer show a window the API would not default
to, until a date picker exists. Nothing wants that today.

## Risks / Trade-offs

**The default response is unbounded and there is no pagination.** → Two hundred
matches is fine; a season of accumulated live runs would not be. This change makes
the unbounded path the *default* one, which raises the odds of meeting the limit.
Not fixed here, because pagination is a contract decision with its own arguments,
and because the store-accumulation question above is upstream of it.

**Two notions of "now" in one codebase.** → A reader who finds the fixture anchor
without its docstring will read it as the bug this change was supposed to fix.
Mitigated by keeping the explanation adjacent to the constant, by `CLAUDE.md`, and
by a test that fails if the offline path stops being reproducible.

**Live runs now write a new `collection_run` row each time instead of overwriting
`demo`.** → Correct, and it means the table grows where it previously did not.
Small, and the alternative is a run record that cannot answer "what happened last
Tuesday".

**Scores from before this change carry the old constant `computed_at`.** → They are
append-only and stay. A live run after this change writes a *later* timestamp, so
serving reads resolve to the new rows correctly. Rows written before it remain
mutually tied, which is the pre-existing condition rather than something introduced
here. No migration: rewriting history in an append-only store to make old rows look
like they were computed at a time they were not would be worse than the tie.
