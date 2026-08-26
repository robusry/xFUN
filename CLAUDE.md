# xFUN

Predicting which soccer matches will be entertaining to watch, for viewers in the
US, across leagues people actually follow.

## Read this first

**`openspec/config.yaml` holds the full design context. Read it before doing any
design or implementation work.** It is the authoritative record of what has been
decided and why, what must not be "simplified", and what is still open. This file
is a pointer, plus the operational detail config.yaml does not carry.

**`docs/STUBS.md` says what is real and what is placeholder.** Most of this
repository is deliberately minimal. Read it before assuming anything works.

## Project state

**A walking skeleton with one working model.** Every tier exists and is connected
end to end. `uv run python scripts/pipeline.py` acquires real matches, scores them,
and writes to a SQLite file with no database server, no container, and no
credentials. Most components inside the tiers are still placeholders by design.

**There is no offline mode, and that is the design.** A run acquires from goal.com or
it produces nothing. The pipeline's varying inputs — the clock, the collector's page
source, how canonical matches reach the store, and the slate rule — are arguments to
`run_pipeline(...)`, not a flag. `main()` supplies live ones; `tests/harness.py`
supplies captured ones for CI. That is the whole difference, and it exists so the
thing a person runs and the thing CI exercises cannot become two systems.

Two of the three registered models predict nothing. Three of four calibration cohorts
and two of three composition policies return 501.

**What is real runs from the source to the score.** Acquisition brings in real
upcoming matches and their US broadcasters, and `recent-results` collects the goals
each side scored in its last five completed matches, which `recent-goals-total` sums
into the only score in this repository computed from real data. It is unvalidated —
nothing here has been tested against whether a match was enjoyable, and nothing can be
until there is a label. Matches where a side has fewer than five completed matches
come back with a recorded skip reason and no score, which is the partial-coverage path
working on real data.

`openspec/specs/` is the authoritative record of what the system currently
**does** — eleven capabilities, 71 requirements — while `openspec/config.yaml`
holds the reasoning behind them. Archived changes are under
`openspec/changes/archive/`:

- `2026-08-01-establish-project-structure` — the architecture, the workflow, and
  the skeleton itself
- `2026-08-02-add-collector-tier` — the collector tier, the slate, and the entity
  joins
- `2026-08-03-add-live-schedule` — real matches and US broadcasters, the
  `us-watchable` slate rule, and the six-source survey behind picking goal.com
- `2026-08-05-add-recent-goals-model` — the first real collector and the first
  model with real inputs, the 120-day lookback and the coverage curve behind it,
  and why fewer than five matches must produce absence rather than a partial sum
- `2026-08-23-add-collector-corpora` — persisted collector output and the
  freshness rule that decides whether a collector runs at all, why reuse requires
  entity coverage as well as age, and why a failed collector is not served its own
  stale corpus
- `2026-08-24-use-real-dates` — where a run's notion of "now" comes from, why the
  offline anchor stays frozen while a real run reads the clock, and why an omitted
  date bound means unbounded rather than a server-chosen window
- `2026-08-25-make-pipeline-live-only` — why the demo concept was removed, why the
  offline path became injected arguments rather than a flag, why captured
  third-party bytes left `contracts/`, and what the loss of the offline clone bought

**This file does not set priorities.** "Still open" below records what is
undecided, not a queue. Ask what the session is for rather than inferring it.

## The design in one paragraph

Several models, developed independently, each score a match. Their **raw scores
are the only truth** — stored append-only, never updated. Calibration and
composition happen at **read** time, because the caller chooses the calibration
cohort per request, so a calibrated score is not a property of a stored row.
Models are pure functions that declare which snapshot features they need; matches
missing those features are skipped with a recorded reason, which is routine rather
than exceptional. Fetching is not eliminated but moved earlier, into **collectors**
— the one tier allowed to touch the network. A collector receives the whole slate,
chooses its own fan-out, and keys its output by match, team, or league for the
platform to join on mechanically, so a source is fetched once no matter how many
models read it and attribution stays a model's judgement rather than a collector's. How scores are blended is versioned configuration behind a
repointable alias, so the blending decision stays cheap to change — which is the
point, because it is expected to change repeatedly.

## Do not "fix" these

Full list with rationale is in `openspec/config.yaml`. The ones most likely to
look like bugs:

- **Calibrated and composed scores are not stored.** Deriving them per request is
  the design, not a missing optimisation.
- **Models return unnormalised `raw_score` on arbitrary scales.** Normalising in
  the model is forbidden; the platform percentile-ranks.
- **There is no update or delete path for scores.** Database triggers enforce it.
- **The API imports no model package.** CI fails if one appears.
- **Unimplemented cohorts/policies raise rather than falling back**, and surface
  as 501.
- **Matches with no score are still returned**, with a reason.
- **The blend weights are somewhat arbitrary, on purpose.** The team picks which
  models count and how much by argument, and changes its mind with a recipe diff.
  Validating the formula against a ground-truth label for "entertaining" is not a
  goal here, so "these weights are unjustified" is a description of the design
  rather than a defect to open a change against. Models still say plainly in their
  READMEs that they are arguments and not findings — that honesty is the part that
  is load-bearing.
- **Collectors and the schedule source are exempt from the purity check.**
  Touching the network is the purpose of those two tiers, and there are exactly
  two, separated by when they run relative to the slate: the schedule source
  produces it, collectors enrich it. A collector cannot produce the slate —
  `collect(slate)` takes one as input. The rule points the other way: no model and
  no API package may import either.
- **A signal path never names its producer.** `signals.<namespace>.<leaf>`, where
  the namespace is a subject area. Encoding the producer would make swapping one a
  breaking change for every model declaring the path.
- **A collector nothing declares is not run**, and that is recorded rather than
  omitted — "no consumer" is a different answer from "ran and found nothing".
- **Collector failure is not absence.** Both leave the same hole in the snapshot;
  only the run record can tell them apart, so it does.
- **The offline harness's timestamps are frozen and must stay frozen.**
  `OFFLINE_STAMP`, `OFFLINE_RUN_ID`, and `OFFLINE_AS_OF` in `tests/harness.py` look
  exactly like the hardcoded dates `use-real-dates` removed from the live path, and
  they are the opposite thing. The captured result pages exist only for a bounded
  range of dates, so a scan anchored to today walks off the end of them and reports an
  absence that is an artefact of the anchor. The end-to-end test also compares
  successive runs against each other, which a moving clock would break daily. The
  offline harness is a *reproduction*, not a simulation of today.
- **The pipeline has no `--offline` flag and must not grow one.** A mode a person can
  select is a mode that drifts away from the one CI exercises, which is exactly the
  state `make-pipeline-live-only` ended: the fixture path was what everyone ran and
  what CI checked, while the live path — the actual product — was tested by nothing.
  `test_the_pipeline_offers_no_offline_mode` fails if a flag reappears.
- **`fixture-signals` and `social-buzz` are registered by nothing that runs.** They
  are not dead code awaiting deletion. They exercise all three entity joins, and
  `fixture-team` returns one team on purpose so the partial-coverage path has a case
  where a match carries `signals.reddit.home.*` with no `away` counterpart — nothing
  else in the repository produces that shape. They are registered only by
  `tests/harness.py`, because a collector that invents its values must never write
  into the same corpus as one that collected them: no row records which kind it is.
- **Corpus freshness is measured against an injected timestamp, never the clock.**
  `run_collectors` takes `started_at` and compares it to the stored `collected_at`.
  Calling `datetime.now()` there would make the invocation decision depend on when
  the test happened to run, which is the property that makes the tier testable at
  all. It looks like an oversight; it is `add-collector-corpora` design D4.
- **Reuse requires coverage as well as freshness.** A collector is skipped only if
  its corpus is inside its window *and* holds a row for every entity the slate
  asks about. Dropping the second check looks like a cheap win and would let an
  unseen entity's gap be served as though the source had answered.
- **A failed collector does not fall back to its stored corpus.** Tempting, and
  deferred on purpose: a score computed from yesterday's signals is a different
  claim from one computed today, and no score row records which it was. That needs
  `add-score-provenance` first.

## Layout

```
contracts/          the seam: JSON Schemas, openapi.yaml, golden fixtures
packages/
  scoring-contract/   model interface + types. no deps, no I/O.
  scoring-runtime/    registry, collection, entity joins, runner, calibration
  store/              canonical entities + append-only score store
  models/<id>/        one package per model, deps isolated
  collectors/<id>/    one package per data source. ONE of the two tiers
                      that may touch the network. purity-exempt by design.
                      (the other is ingestion/schedule/, which runs BEFORE
                      the slate because it produces what the slate is made of)
  composition/        src/ = mechanism (Zone A), recipes/ = values (Zone C)
  ingestion/          slate assembly + canonical entity writing
  api/                FastAPI, read-only
  web/                Vite + React, one page
  clients/ts/         generated from openapi.yaml
infra/migrations/   plain .sql, applied in filename order
docs/               architecture, workflow, zones, STUBS
scripts/            pipeline, capture tools, and the CI check scripts
tests/              captures/  third-party bytes, read only by tests
                    harness.py the one description of "the pipeline, offline"
```

## Setup and verification

```bash
uv sync --all-packages    # NOT plain `uv sync` — that installs only the root
pnpm install
pnpm client:generate      # types from contracts/openapi.yaml; gitignored
```

Everything CI runs, in the order it runs:

```bash
uv run python scripts/check_dependencies.py      # tier boundaries
uv run ruff check .
uv run pytest -q                                 # 250 tests, includes the offline
                                                 # end-to-end pipeline run
uv run python scripts/check_api_conformance.py   # responses match the contract
uv run python scripts/validate_contracts.py      # fixtures match the schemas
pnpm -r typecheck && pnpm web:build
openspec validate --all --strict
```

Both lockfiles are committed and CI installs with `--locked` / `--frozen-lockfile`.
After changing a Python dependency, run `uv lock` and commit the result.

Three checks exist because the rules they enforce are easy to break by accident
and hard to notice afterwards — model purity, the API not importing a model, and
live responses matching `contracts/openapi.yaml`. Do not weaken them to make a
change pass.

## Code conventions

- Python 3.12, `from __future__ import annotations`, `collections.abc` for ABCs.
- Comments explain **why**, especially where the code looks unnecessarily
  indirect. Most of the surprising code here is deliberate.
- A model depends on `xfun-scoring-contract` and nothing else.
- Anything placeholder says so in its module docstring, its package README, and
  `docs/STUBS.md`. An unmarked stub is worse than a missing feature.

## Workflow

Full detail in `docs/workflow.md`; zones in `docs/zones.md`.

- **Branch before touching any file**, including before `openspec new change`.
  `change/<id>`, `capture/<id>`, or `chore/<slug>`.
- One change = one branch = one PR.
- **The PR opens only when the change is complete** — artifacts, implementation,
  and the archive commit. Push WIP to the branch freely; the absence of a PR is
  what signals "not ready".
- Rebase on `main`, then `openspec archive`, then open the PR.
- Conventional Commits. `spec` is a valid type, for planning and archive commits.
  The PR title matters most — squash-merge makes it the commit subject.
- Not every change needs specs. `docs/zones.md` says which do.

Decisions are made by the team as a group; PR approval is the deciding gate. No
individual owns any part of this project.

## Still open

Not a queue — nothing here is claimed as next.

- **What "fun" means** — as an argument to be had, not a number to be measured.
  Which models blend at which weights is the team's call, settled by discussion
  and changed with a one-line recipe diff. See "Do not 'fix' these" above: the
  weights being somewhat arbitrary is accepted, not a gap awaiting an evaluation
  harness.
- **Liga MX reaches the slate, but on borrowed time.** This entry previously said
  it was permanently absent; that was corrected on 2026-08-23, when a live run
  showed goal.com naming per-match providers for every Liga MX and Femenil fixture
  (ViX, TUDN, Fubo, FOX Deportes, Estrella TV). They resolve on the per-match path
  and need no rights-table entry. **Do not "fix" anything by adding a league-wide
  Liga MX entry**: its US rights are still held per club — TelevisaUnivision
  carries most, Chivas home matches are Telemundo/Peacock,
  Monterrey/Tijuana/Santos are FOX — so no league-wide line is true, and a
  confidently wrong provider is the failure a viewer notices immediately. What is
  still open is that this rests entirely on an unofficial source choosing to
  answer; when it stops, those matches resolve to `unknown` and drop off again.
  Club-level entries or the per-match manual-entry path below are the durable
  answers, and neither is proposed. Full detail in `docs/STUBS.md` and the
  archived `add-live-schedule` design, D3.
- **A way for a person to enter missing TV data by hand**, per match rather than
  per league. The rights table is the league-wide case of this. Liga MX remains
  the standing example of what it cannot express, even though the source happens
  to be covering that gap today — which is the argument for the manual path rather
  than against it.
- Global versus personalised as the headline score.
- League scope: audience size versus entertainment density.
- The default calibration cohort, once more than one exists.
- Whether `default` carries a stability promise for third parties.

## Absent on purpose, not forgotten

`docs/STUBS.md` is authoritative. In short: no *validated* model, no odds and no
league table for the models that need them, no mobile app, and no automated
JavaScript test — CI covers the TS side with typecheck and build only. There is no
evaluation harness either, but that one is a decision rather than an absence: see
"Do not 'fix' these".

Matches, US broadcasters, and recent goals ARE real — there is no other path — all via
goal.com — an unofficial source with no API contract, chosen from a six-way survey
recorded in the archived `add-live-schedule` design, D2. Read that before proposing
a replacement; most of the obvious candidates refuse automated access, and
`add-recent-goals-model` design D1 records why a *second* source is worse than it
looks: matching another provider's team names to this project's would be silent
when it got one wrong. The project now depends on it wholly: with the fixture-backed
path gone, a goal.com outage means a run produces nothing and there is no local
workaround. That was accepted knowingly in `make-pipeline-live-only`, D7.

Branch protection on `main` is enabled. Adding `contracts`, `ci`, and `pr-hygiene`
as required status checks is still outstanding.
