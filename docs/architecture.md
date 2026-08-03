# Architecture

## The tiers

```
┌──────────────────────────────────────────────────────────────────┐
│ INGESTION          scheduled · idempotent · slate + canonical rows│
│  ├ schedule source  which matches exist, and who carries them.    │
│  │                  TOUCHES THE NETWORK — runs before the slate,  │
│  │                  because it produces what the slate is made of │
│  └ fixture files    the default path; no network, no credentials  │
└────────────────────────────┬─────────────────────────────────────┘
                             │ canonical entities
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ STORE              league · team · match · odds · form · table    │
└────────────────────────────┬─────────────────────────────────────┘
                             │ Slate                ◀── contract 1a
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ COLLECTORS         the other tier allowed to touch the network.   │
│                    each fans out its own way, once per slate      │
│                    keyed by  match · team · league                │
└────────────────────────────┬─────────────────────────────────────┘
                             │ entity-keyed values
                    ┌────────▼─────────┐
                    │  mechanical join │  match → identity
                    │                  │  team  → {home, away}
                    │                  │  league→ broadcast
                    └────────┬─────────┘
                             │ MatchSnapshot        ◀── contract 1
                             │ (canonical + signals.*)
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ MODELS             pure functions. no I/O. mutually independent.  │
│                    over-under-lean  odds-spread  social-buzz      │
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

## Where fetching happens, and why it is not in the model

A model may not touch the network — that purity is what makes a score
reproducible. But a model developer still needs to bring new data, and asking
another tier to add a schema field for every experiment makes changing your mind
expensive, which is the one thing this project optimises against.

Collectors resolve that. Fetching moves **earlier** rather than being eliminated:

- **The slate arrives whole**, so each collector picks its own fan-out. An odds
  source is queried per match; a social source is read per team; a league table is
  one request covering twenty matches.
- **Output is keyed by entity, not always by match.** Requiring per-match output
  would force every collector to solve attribution — and attribution is a judgement
  call. One model wants strict match-thread matching, another wants loose
  team-mention sentiment; a collector that picks one forecloses the other.
- **A collector runs once per slate**, no matter how many models read it, and not
  at all if nothing does.
- **A path has exactly one producer**, but a namespace is a subject area rather
  than a producer id. So a signal can change producer without its path moving, and
  models that declare the path never notice. Provenance lives in the run record.

The tier boundary is enforced in the inverse direction from everywhere else: CI
does not check what a collector imports — reaching outside is its purpose — it
checks that **no model and no API package imports a collector**.

### The two tiers that fetch, and why there are two

External access lives in exactly two places, and which one a job belongs to is
decided by **when it runs relative to the slate**:

| | runs | produces |
|---|---|---|
| **schedule source** | before a slate exists | the matches a slate is made of, and who broadcasts them |
| **collectors** | after the slate is assembled | signals about matches already known |

The split is structural rather than stylistic. `Collector.collect(slate)` takes a
slate as its input, so nothing expressible through that interface can produce one —
a schedule source forced into it would have to be handed a slate it then ignored.
`assemble_slate()` reads the `match` table, which has to be populated first.

So "collectors are the only tier that may touch the network" is now false, and the
rule that replaced it is narrower rather than looser: **two named tiers, in a stated
order, and nothing else** — no model, no API, no composition, no store. CI checks
that scoring and serving reach neither.

### Absence and failure are different answers

"This match has no thread" is permanent and correct. "The API returned 503"
establishes nothing. Both leave an identical hole in the snapshot, so the run
record separates them and the skip reason carries which one it was. Without that,
a source down for a week looks exactly like a source with nothing to say.

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
