# tests/captures/

Captured responses from somebody else's system, kept so that CI can exercise the
code that reads them without contacting anyone.

**Nothing a user runs reads these files.** The pipeline always acquires from the live
schedule source. These exist for the test suite and for nothing else.

## Why they are not in `contracts/`

`contracts/` is the seam between our own tiers: every file in it is authored by this
project, validated against a JSON Schema in CI, and used by both sides of an interface
as the agreed definition of that interface. A failing fixture there means one of our
producers violated a contract.

These files are the opposite of that on every count. They are goal.com's bytes, not
ours. They validate against no schema, because their shape is not ours to define. They
are not an agreement between anyone — they are a photograph of what a third party
happened to serve on a particular day, and they are replaced wholesale when that
changes. A failing capture here means somebody else changed their website.

Mixing the two in one directory made it impossible to tell, from a file's location,
which kind of failure you were looking at.

## What is here

```
goal-com/
  2026-08-22-dense.html     a busy schedule page, most parser tests run on this
  2026-08-12-sparse.html    a thin one, for the between-seasons case
  malformed-state.html      deliberately broken, so the parser is checked for
                            failing loudly rather than reporting an empty window
  results/                  49 dated result pages, Apr-Aug 2026
```

`results/` is what lets the end-to-end test run the real `recent-results` scan over
real historical results with no network. Its depth is not arbitrary: the pages walk
back from 2026-08-14 far enough for each of the sixteen teams in
`contracts/fixtures/snapshots/` to have five completed matches, which is the same
stopping rule the collector uses. Removing pages from the tail will make that scan
report an absence that is an artefact of the capture rather than a fact about
anything.

## Regenerating

Both tools are development-only, run by hand, and not part of the pipeline or CI:

- `scripts/capture_schedule_fixture.py` writes the dated pages in `goal-com/`
- `scripts/capture_results_fixture.py` writes `goal-com/results/`

Both write **reduced** captures — a live page is 0.5-3 MB, almost all of it markup and
competitions nothing here reads. What survives is the source's own bytes for a chosen
subset, never a paraphrase.

## These go stale silently

Nothing detects it when goal.com changes shape. These captures will keep passing their
tests long after the live source stops matching them, and the only signal is a live run
failing. That is a known limit, recorded in the archived `make-pipeline-live-only`
design, D5.
