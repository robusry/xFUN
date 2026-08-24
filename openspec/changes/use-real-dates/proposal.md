## Why

`scripts/pipeline.py` hardcodes a single timestamp and a single run identifier and
uses both on every path, including `--live`:

```python
STAMP = "2026-08-14T04:00:00+00:00"        # computed_at, and the run's start and end
run_id="demo"                               # every run, forever
```

A live run today therefore writes scores stamped nine days ago under a run id that
overwrites its predecessor. `packages/web/src/App.tsx:23` hardcodes a matching
`2026-08-01`–`2026-08-31` window, whose own comment says "Real date handling
arrives with real ingestion".

Three things are already broken by this, in ascending order of how quietly:

1. The page will show an empty list on 1 September, and shows five fewer matches
   than exist today.
2. `add-collector-corpora` shipped a freshness rule that cannot fire. Every corpus
   row reads as zero seconds old because it is compared against a constant, so
   after the first run every collector reuses forever unless `--refresh` is passed.
3. `score-store` requires serving reads to resolve the current score per model
   "based on `computed_at`". With one constant timestamp, every generation ties,
   and which row wins is an accident of insertion order.

## What Changes

- **A run's timestamps come from the run.** The live path reads the clock once, at
  the start, and injects that value everywhere a timestamp is needed. Nothing
  downstream starts reading the clock — `run_collectors` and `run_models` keep
  taking injected values, which is what makes them reproducible.
- **The fixture path stays frozen, deliberately.** It keeps a fixed anchor so the
  offline demo and CI remain byte-for-byte reproducible. `OFFLINE_AS_OF` does not
  move: the golden result captures were walked back from it, and a scan starting
  anywhere else drifts off the end of them.
- **Run identifiers become unique per run** on the live path, derived from the run
  timestamp. The fixture path keeps a deterministic id so repeat offline runs stay
  idempotent.
- **`from` and `to` become optional** on `GET /v1/matches`. Omitted, the API
  answers over the range the store actually holds. **The response states the window
  it used**, for the same reason it already states its cohort and alias: a caller
  that did not choose the window cannot interpret the answer without being told.
- **The web page stops hardcoding a window.** It asks for none and renders what it
  is given.

Not in scope: the store accumulates matches across runs, so eight fixture matches
now sit alongside live ones. Real, and left alone — separating them needs a
decision about whether the two paths should share a store at all, which is a
larger question than timestamps.

## Capabilities

### New Capabilities

None. This change makes existing requirements effective rather than adding
behaviour.

### Modified Capabilities

- `public-api`: the match-list date range becomes optional, and the response
  declares the window it served.
- `schedule-acquisition`: "The system runs without network access or credentials"
  gains the reproducibility half — the fixture path is anchored to a fixed point
  and repeat runs are identical, while the live path takes its time from the run.
- `data-collection`: "A collection run is recorded" requires run identifiers to
  distinguish runs, so that two runs are two records rather than one overwritten
  one.
- `score-store`: "Serving reads resolve to the current score per model" requires
  `computed_at` to distinguish generations, without which "most recent" has no
  meaning.

## Impact

**Zone A** — `contracts/openapi.yaml` (optional parameters, new response field) and
the `MatchListResponse` schema. Specs required.

**Zone B** — `packages/api/` (default window, declare it in the response).

**Zone C** — `packages/web/`, and `scripts/pipeline.py`.

Affected code:

- `scripts/pipeline.py` — `STAMP` and `run_id="demo"` become run-derived on the
  live path; `OFFLINE_AS_OF` and the fixture anchor stay.
- `packages/api/src/xfun_api/main.py` — `date_from`/`date_to` optional; the served
  window reported.
- `contracts/openapi.yaml` and `contracts/schemas/` — parameters no longer
  required; response gains the window.
- `packages/clients/ts/` — regenerated, not hand-edited.
- `packages/web/src/App.tsx` — `FROM`/`TO` deleted.
- `docs/STUBS.md` — resolves "one hardcoded date window matching the fixtures"
  under **The web page**. Routing, a date picker, and filtering stay unresolved.
- The `add-collector-corpora` risk about TTL never firing is retired by this
  change; its archived design says so and should not be edited.
