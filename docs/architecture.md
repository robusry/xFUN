# Architecture

## The tiers

```
┌──────────────────────────────────────────────────────────────────┐
│ INGESTION          scheduled · idempotent · one adapter per source│
│                    fixture-file only, for now                     │
└────────────────────────────┬─────────────────────────────────────┘
                             │ canonical entities
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ STORE              league · team · match · odds · form · table    │
└────────────────────────────┬─────────────────────────────────────┘
                             │ MatchSnapshot        ◀── contract 1
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ MODELS             pure functions. no I/O. mutually independent.  │
│                    over-under-lean   odds-spread                  │
└────────────────────────────┬─────────────────────────────────────┘
                             │ ModelScore           ◀── contract 2
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ SCORE STORE        append-only. never updated, never deleted.     │
│                    (match, model, version, snapshot_hash)         │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │ calibrate(cohort)│   at READ time
                    │ compose(recipe)  │   — never stored
                    └────────┬─────────┘
                             │ OpenAPI              ◀── contract 3
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ API                read-only · versioned · runs no models         │
└──────┬─────────────────────┬──────────────────────┬──────────────┘
       ▼                     ▼                      ▼
     web                mobile (later)         third parties
```

## Four decisions that explain most of the code

### 1. Scores are precomputed in batch. The API never runs a model.

Fixtures are known days ahead and odds move on a schedule, so there is no
request-time input to scoring. Scheduled jobs write scores; the API reads them.

This is what makes the modelling genuinely independent rather than nominally so.
Model runtime and API runtime share nothing — a model can be a cron job, a
notebook, or a service in another language, and the API does not notice. A broken
model degrades score freshness, not availability.

`scripts/check_dependencies.py` enforces it: the API package cannot declare or
import any model package.

### 2. Raw model scores are the only truth.

Because the **calibration cohort is chosen by the caller per request**, a
calibrated score is not a property of a stored row — the same raw score yields
different calibrated values under different cohorts.

```
   TRUTH (stored, append-only)        DERIVED (computed at read, cacheable)
   ───────────────────────────        ─────────────────────────────────────
   raw model scores       ──────▶     calibrate(cohort) ──▶ compose(recipe) ──▶ rank
```

This is simpler than storing both, not more complex: there is exactly one source
of truth, and any materialisation is a cache that can be thrown away.

### 3. Models are pure and know nothing about each other.

A model takes a `MatchSnapshot` and returns a `ScoreResult`. No network, no
database, no clock. It declares which snapshot features it needs, and the runtime
skips matches where those are unavailable — recording the skip rather than
swallowing it.

Coverage gaps are routine, not exceptional. Of the seven fixture matches, one has
a total line but no moneyline (scored by one model, skipped by the other) and one
has no odds at all (scored by neither, returned with a reason).

Mutual independence keeps scoring a flat fan-out. One model reading another's
output would make backfills ordered and composition expensive to reverse.

### 4. Composition is configuration, and public names are repointable.

A recipe names models, weights, a missing-model policy, and a minimum count. It
lives in `packages/composition/recipes/*.yaml` and changing it is a config diff —
no code, no model re-runs. Recomposing the entire history is arithmetic over rows
that already exist.

Consumers address `default`, never `default-v1`. Repointing the alias changes what
everyone receives with no client change:

```
   client asks for  ──▶  score=default
                            │
                       alias resolver        ← repoint anytime
                            ▼
                     recipes/default.yaml v1
```

The same mechanism serves a single model's score through the identical code path,
which is what lets the "how do we blend these?" decision stay open indefinitely —
and lets third parties build their own blends from the per-model scores the API
exposes alongside the composite.

## Why calibration exists at all

Models emit raw scores on whatever scale suits them. `over-under-lean` returns a
goals line (2.0–3.5). `odds-spread` returns a normalised entropy (0.0–1.0).
Averaging those directly would be meaningless, and the failure would be silent —
plausible-looking numbers that are quietly nonsense.

So the platform percentile-ranks each model's raw scores within a cohort, per
`(model_id, model_version)`. Every calibrated score travels with the cohort that
produced it, because without it the number cannot be interpreted.

## What is not built yet

Every tier above exists and is connected, but the components inside them are
deliberately minimal. **`docs/STUBS.md` is the authoritative list** of what is
placeholder and which change replaces it.
